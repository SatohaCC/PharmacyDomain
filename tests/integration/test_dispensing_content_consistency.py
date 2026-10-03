"""調剤薬品の対応拒否で本番スコープの永続化状態が変わらないことを検証する。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control.models import ResolvedActorContext
from app.application.access_control.policy import AuthorizationService
from app.application.dispensing.get_dispensing import GetDispensingQuery
from app.application.dispensing.inputs import SubstitutionInput
from app.application.dispensing.list_dispensings_by_prescription import (
    ListDispensingsByPrescriptionQuery,
)
from app.application.dispensing.record_dispensed_content import (
    RecordDispensedContentCommand,
)
from app.application.dispensing.start_dispensing import StartDispensingCommand
from app.domain.dispensing.exceptions import (
    SubstitutionOriginalMismatchError,
    SubstitutionRequiredError,
)
from app.domain.dispensing.primitives import DispensingId
from app.domain.prescription.prescription import Prescription
from app.domain.store.manager_assignment import (
    ManagerAssignmentPeriod,
    StoreManagerAssignment,
    StoreManagerAssignmentId,
)
from app.infrastructure.di.root import PostgresCompositionRoot
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories.repository_set import (
    PostgresRepositorySet,
)
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from tests.application.dispensing.helpers import create_medicine_input, create_rp_input
from tests.factories.prescription_factory import (
    create_medicine,
    create_prescription,
    create_rp,
)
from tests.fakes.stub_actor_context_provider import VALID_TOKEN
from tests.integration.dispensing_content_helpers import snapshot_dispensing_persistence
from tests.integration.test_clinical_transaction_http import setup_clinical


@dataclass(frozen=True)
class DispensingContentFixture:
    """本人・薬剤師・管理薬剤師と保存済み原本を備えた本番実行の前提。"""

    root: PostgresCompositionRoot
    authorization: AuthorizationService
    actor: ResolvedActorContext
    prescription: Prescription


async def setup_dispensing_content(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> DispensingContentFixture:
    """既存臨床前提を再利用し、未調剤の対象処方と管理薬剤師を保存する。"""
    clinical = await setup_clinical(engine, session_factory)
    state = getattr(clinical.app.state, STATE_ATTRIBUTE)
    assert isinstance(state, PresentationState)
    assert state.composition_root is not None
    actor = await state.actor_provider.authenticate(VALID_TOKEN)
    assert isinstance(actor, ResolvedActorContext)
    assert actor.staff_id is not None
    prescription = create_prescription(
        corporate_id=clinical.corporate_id,
        store_id=clinical.prescription.store_id,
        patient_id=clinical.prescription.patient_id,
        document_number="9876543210123456",
    ).ready_for_dispensing()
    async with PostgresUnitOfWork(session_factory) as work:
        repositories = PostgresRepositorySet.create(work)
        await repositories.manager_assignment.save(
            StoreManagerAssignment(
                id=StoreManagerAssignmentId.generate(),
                corporate_id=clinical.corporate_id,
                store_id=prescription.store_id,
                staff_id=actor.staff_id,
                person_id=clinical.person.id,
                period=ManagerAssignmentPeriod(starts_on=date(2026, 1, 1)),
            )
        )
        await repositories.prescription.save(prescription)
        await work.commit()
    return DispensingContentFixture(
        root=state.composition_root,
        authorization=AuthorizationService(actor),
        actor=actor,
        prescription=prescription,
    )


@pytest.mark.parametrize(
    ("has_substitution", "expected_error"),
    [
        pytest.param(False, SubstitutionRequiredError, id="代替なし同名異コード"),
        pytest.param(True, SubstitutionOriginalMismatchError, id="不正原本引用"),
    ],
)
async def test_実DB調剤開始_薬品対応不整合_別スコープで全保存状態と原本監査を保持する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    has_substitution: bool,
    expected_error: type[SubstitutionRequiredError]
    | type[SubstitutionOriginalMismatchError],
) -> None:
    # Arrange
    fixture = await setup_dispensing_content(engine, session_factory)
    prescription = fixture.prescription
    assert fixture.actor.staff_id is not None
    query = ListDispensingsByPrescriptionQuery(
        corporate_id=str(prescription.corporate_id.value),
        prescription_id=str(prescription.id.value),
    )
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        listed_before = await scope.use_cases.dispensing.list_by_prescription.execute(
            query
        )
        original_before = await scope.repositories.prescription.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
    assert original_before is not None
    assert listed_before == ()
    saved_before = await snapshot_dispensing_persistence(engine)
    assert saved_before["dispensing_processes"]
    substitution = (
        SubstitutionInput(
            category="generic_substitution",
            original_code_type="yj",
            original_code="2171022F1045",
            original_name="別の原本薬品",
        )
        if has_substitution
        else None
    )
    command = StartDispensingCommand(
        corporate_id=str(prescription.corporate_id.value),
        store_id=str(prescription.store_id.value),
        prescription_id=str(prescription.id.value),
        dispenser_id=str(fixture.actor.staff_id.value),
        iteration=1,
        dispensed_date=date(2026, 8, 24),
        dispensed_rps=(
            create_rp_input(
                medicines=(
                    create_medicine_input(
                        code="2171022F1037",
                        name=prescription.rps[0].medicines[0].name.value,
                        substitution=substitution,
                    ),
                )
            ),
        ),
    )

    # Act / Assert: 例外をスコープ外で捕捉し、正常終了へ流さない。
    with pytest.raises(expected_error):
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.dispensing.start.execute(command)
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        listed_after = await scope.use_cases.dispensing.list_by_prescription.execute(
            query
        )
        original_after = await scope.repositories.prescription.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
    assert listed_after == listed_before
    assert original_after is not None
    assert asdict(original_after) == asdict(original_before)
    assert await snapshot_dispensing_persistence(engine) == saved_before


@pytest.mark.parametrize(
    ("has_substitution", "expected_error"),
    [
        pytest.param(False, SubstitutionRequiredError, id="代替なし同名異コード"),
        pytest.param(True, SubstitutionOriginalMismatchError, id="不正原本引用"),
    ],
)
async def test_実DB調剤更新_薬品対応不整合_別スコープで内容状態世代原本監査を保持する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    has_substitution: bool,
    expected_error: type[SubstitutionRequiredError]
    | type[SubstitutionOriginalMismatchError],
) -> None:
    # Arrange
    fixture = await setup_dispensing_content(engine, session_factory)
    prescription = replace(
        fixture.prescription,
        rps=(
            create_rp(
                medicines=(
                    create_medicine(),
                    create_medicine(line_number=2, code="2171022F1045", name="薬C"),
                )
            ),
        ),
    )
    async with PostgresUnitOfWork(session_factory) as work:
        repository = PostgresRepositorySet.create(work).prescription
        await repository.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
        await repository.save(prescription)
        await work.commit()
    assert fixture.actor.staff_id is not None
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        started = await scope.use_cases.dispensing.start.execute(
            StartDispensingCommand(
                corporate_id=str(prescription.corporate_id.value),
                store_id=str(prescription.store_id.value),
                prescription_id=str(prescription.id.value),
                dispenser_id=str(fixture.actor.staff_id.value),
                iteration=1,
                dispensed_date=date(2026, 8, 24),
                dispensed_rps=(
                    create_rp_input(
                        medicines=(
                            create_medicine_input(
                                preparations=("unit_dose_packaged", "compounded")
                            ),
                            create_medicine_input(
                                line_number=2, code="2171022F1045", name="薬C"
                            ),
                        )
                    ),
                ),
            )
        )
    query = GetDispensingQuery(
        corporate_id=str(prescription.corporate_id.value), dispensing_id=started.id
    )
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        before = await scope.use_cases.dispensing.get.execute(query)
        original_before = await scope.repositories.prescription.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
    assert original_before is not None
    assert len(before.dispensed_rps[0].medicines) == 2
    assert before.dispensed_rps[0].medicines[0].preparations
    saved_before = await snapshot_dispensing_persistence(engine)
    assert saved_before["operation_audits"]
    substitution = (
        SubstitutionInput(
            category="generic_substitution",
            original_code_type="yj",
            original_code="2171022F1053",
            original_name="別の原本薬品",
        )
        if has_substitution
        else None
    )
    command = RecordDispensedContentCommand(
        corporate_id=str(prescription.corporate_id.value),
        dispensing_id=started.id,
        dispensed_rps=(
            create_rp_input(
                medicines=(
                    create_medicine_input(
                        code="2171022F1037",
                        name=prescription.rps[0].medicines[0].name.value,
                        substitution=substitution,
                    ),
                )
            ),
        ),
    )

    # Act / Assert
    with pytest.raises(expected_error):
        async with fixture.root.request_scope(
            authorization=fixture.authorization
        ) as scope:
            await scope.use_cases.dispensing.record_dispensed_content.execute(command)
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        after = await scope.use_cases.dispensing.get.execute(query)
        original_after = await scope.repositories.prescription.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
    assert asdict(after) == asdict(before)
    assert original_after is not None
    assert asdict(original_after) == asdict(original_before)
    assert await snapshot_dispensing_persistence(engine) == saved_before


async def test_実DB調剤開始_正当な代替_別スコープで全代替入力と原本と成功監査を保持する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_dispensing_content(engine, session_factory)
    prescription = fixture.prescription
    assert fixture.actor.staff_id is not None
    before = await snapshot_dispensing_persistence(engine)
    command = StartDispensingCommand(
        corporate_id=str(prescription.corporate_id.value),
        store_id=str(prescription.store_id.value),
        prescription_id=str(prescription.id.value),
        dispenser_id=str(fixture.actor.staff_id.value),
        iteration=1,
        dispensed_date=date(2026, 8, 24),
        dispensed_rps=(
            create_rp_input(
                medicines=(
                    create_medicine_input(
                        code="2171022F1037",
                        name="アムロジピンＯＤ錠２．５ｍｇ「サワイ」",
                        substitution=SubstitutionInput(
                            category="generic_substitution",
                            original_code_type="yj",
                            original_code="2171022F1029",
                            original_name="ノルバスク錠2.5mg",
                            reason="患者希望による後発品変更",
                            inquiry_number=None,
                        ),
                    ),
                )
            ),
        ),
    )

    # Act
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        started = await scope.use_cases.dispensing.start.execute(command)
    dispensing_id = DispensingId.parse(started.id)
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        actual = await scope.use_cases.dispensing.get.execute(
            GetDispensingQuery(
                corporate_id=str(prescription.corporate_id.value),
                dispensing_id=started.id,
            )
        )
        stored = await scope.repositories.dispensing.get(
            corporate_id=prescription.corporate_id, dispensing_id=dispensing_id
        )
        original = await scope.repositories.prescription.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
    after = await snapshot_dispensing_persistence(engine)

    # Assert
    assert asdict(actual) == asdict(started)
    dto_medicine = actual.dispensed_rps[0].medicines[0]
    assert dto_medicine.code == "2171022F1037"
    assert dto_medicine.substitution is not None
    assert asdict(dto_medicine.substitution) == {
        "category": "generic_substitution",
        "original_code_type": "yj",
        "original_code": "2171022F1029",
        "original_name": "ノルバスク錠2.5mg",
        "reason": "患者希望による後発品変更",
        "inquiry_number": None,
    }
    assert stored is not None
    medicine = stored.dispensed_rps[0].medicines[0]
    assert medicine.identifier.code is not None
    assert medicine.identifier.code.value == "2171022F1037"
    substitution = medicine.substitution
    assert substitution is not None
    assert substitution.category.value == "generic_substitution"
    assert substitution.original_identifier.code_type.value == "yj"
    assert substitution.original_identifier.code is not None
    assert substitution.original_identifier.code.value == "2171022F1029"
    assert substitution.original_name.value == "ノルバスク錠2.5mg"
    assert substitution.reason is not None
    assert substitution.reason.value == "患者希望による後発品変更"
    assert substitution.inquiry_number is None
    assert original is not None
    assert asdict(original) == asdict(prescription)
    assert after["prescriptions"] == before["prescriptions"]
    assert len(after["dispensing_processes"]) == len(before["dispensing_processes"]) + 1
    audit_rows = [
        row
        for row in after["operation_audits"]
        if row["resource_id"] == dispensing_id.value
    ]
    assert len(audit_rows) == 1
    assert audit_rows[0]["person_id"] == fixture.actor.person_id.value
    assert audit_rows[0]["account_id"] == fixture.actor.account_id.value
    assert audit_rows[0]["corporate_id"] == prescription.corporate_id.value
    assert audit_rows[0]["store_id"] == prescription.store_id.value


async def test_実DB調剤更新_正当な代替_同一IDの代替保持と世代増加と原本不変を確認する(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # Arrange
    fixture = await setup_dispensing_content(engine, session_factory)
    prescription = fixture.prescription
    assert fixture.actor.staff_id is not None
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        started = await scope.use_cases.dispensing.start.execute(
            StartDispensingCommand(
                corporate_id=str(prescription.corporate_id.value),
                store_id=str(prescription.store_id.value),
                prescription_id=str(prescription.id.value),
                dispenser_id=str(fixture.actor.staff_id.value),
                iteration=1,
                dispensed_date=date(2026, 8, 24),
                dispensed_rps=(create_rp_input(),),
            )
        )
    dispensing_id = DispensingId.parse(started.id)
    before = await snapshot_dispensing_persistence(engine)
    before_row = next(
        row
        for row in before["dispensing_processes"]
        if row["id"] == dispensing_id.value
    )
    command = RecordDispensedContentCommand(
        corporate_id=str(prescription.corporate_id.value),
        dispensing_id=started.id,
        dispensed_rps=(
            create_rp_input(
                medicines=(
                    create_medicine_input(
                        code="2171022F1037",
                        name="アムロジピンＯＤ錠２．５ｍｇ「サワイ」",
                        substitution=SubstitutionInput(
                            category="generic_substitution",
                            original_code_type="yj",
                            original_code="2171022F1029",
                            original_name="ノルバスク錠2.5mg",
                            reason="患者希望による後発品変更",
                            inquiry_number=None,
                        ),
                    ),
                )
            ),
        ),
    )

    # Act
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        updated = await scope.use_cases.dispensing.record_dispensed_content.execute(
            command
        )
    async with fixture.root.request_scope(authorization=fixture.authorization) as scope:
        actual = await scope.use_cases.dispensing.get.execute(
            GetDispensingQuery(
                corporate_id=str(prescription.corporate_id.value),
                dispensing_id=started.id,
            )
        )
        stored = await scope.repositories.dispensing.get(
            corporate_id=prescription.corporate_id, dispensing_id=dispensing_id
        )
        original = await scope.repositories.prescription.get(
            corporate_id=prescription.corporate_id, prescription_id=prescription.id
        )
    after = await snapshot_dispensing_persistence(engine)

    # Assert
    assert actual.id == updated.id == started.id
    assert asdict(actual) == asdict(updated)
    assert actual.status == started.status
    assert actual.iteration == started.iteration
    assert actual.dispensed_date == started.dispensed_date
    dto_medicine = actual.dispensed_rps[0].medicines[0]
    assert dto_medicine.code == "2171022F1037"
    assert dto_medicine.substitution is not None
    assert asdict(dto_medicine.substitution) == {
        "category": "generic_substitution",
        "original_code_type": "yj",
        "original_code": "2171022F1029",
        "original_name": "ノルバスク錠2.5mg",
        "reason": "患者希望による後発品変更",
        "inquiry_number": None,
    }
    assert stored is not None
    medicine = stored.dispensed_rps[0].medicines[0]
    assert medicine.identifier.code is not None
    assert medicine.identifier.code.value == "2171022F1037"
    substitution = medicine.substitution
    assert substitution is not None
    assert substitution.category.value == "generic_substitution"
    assert substitution.original_identifier.code_type.value == "yj"
    assert substitution.original_identifier.code is not None
    assert substitution.original_identifier.code.value == "2171022F1029"
    assert substitution.original_name.value == "ノルバスク錠2.5mg"
    assert substitution.reason is not None
    assert substitution.reason.value == "患者希望による後発品変更"
    assert substitution.inquiry_number is None
    assert original is not None
    assert asdict(original) == asdict(prescription)
    assert after["prescriptions"] == before["prescriptions"]
    after_row = next(
        row for row in after["dispensing_processes"] if row["id"] == dispensing_id.value
    )
    assert isinstance(before_row["version"], int)
    assert isinstance(after_row["version"], int)
    assert after_row["version"] > before_row["version"]
    assert len(after["dispensing_processes"]) == len(before["dispensing_processes"])
    assert [
        row for row in after["dispensing_processes"] if row["id"] != dispensing_id.value
    ] == [
        row
        for row in before["dispensing_processes"]
        if row["id"] != dispensing_id.value
    ]
