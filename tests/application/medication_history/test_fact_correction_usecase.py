"""薬歴の事実訂正を認可済み業務として保存し、頭書きを再投影する。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib import import_module, util
from typing import Any

import pytest

from app.application.access_control.models import ActorContext, ActorRole
from app.application.access_control.policy import AuthorizationService
from app.application.common.exceptions import ApplicationError
from app.application.common.unit_of_work import UnitOfWork
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.exceptions import (
    MedicationHistoryStaffNotFoundError,
)
from app.domain.care_event.primitives import EventId
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    RequiredCategoryMissingError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    CategoryCatalogId,
    CounselingNote,
    MajorCategoryCode,
    MajorCategoryName,
    MedicationHistoryImportTimestamp,
    MedicationHistorySourceSystem,
    MediumCategoryCode,
    MediumCategoryName,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import (
    CategorizedNote,
    MajorCategoryDefinition,
    MediumCategoryDefinition,
    ProfileUpdateIntents,
)
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
    create_nsips_start_command,
    create_resolved_actor,
)
from tests.domain.medication_history.test_fact_correction import _element_id
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_independent_follow_up_record,
    create_record,
    finalize_record_with_review,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork

_MISSING = object()
_MODULE_NAME = "app.application.medication_history.correct_medication_history_fact"


def _module() -> Any:
    """未作成の UseCase を import エラーではなく公開契約の Red として示す。"""
    assert util.find_spec(_MODULE_NAME) is not None, "薬歴事実訂正 UseCase が必要"
    return import_module(_MODULE_NAME)


def _use_case(
    fixture: MedicationHistoryFixture,
    *,
    actor: ActorContext | None = None,
    unit_of_work: UnitOfWork | None = None,
) -> Any:
    use_case_type = getattr(_module(), "CorrectMedicationHistoryFactUseCase", None)
    assert callable(use_case_type), "薬歴事実訂正 UseCase の公開クラスが必要"
    access = (
        CorporateAccessService(
            fixture.corporate_repository, AuthorizationService(actor)
        )
        if actor is not None
        else fixture.corporate_access
    )
    return use_case_type(
        record_repository=fixture.record_repository,
        profile_repository=fixture.profile_repository,
        corporate_access=access,
        unit_of_work=unit_of_work or NullUnitOfWork(),
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        category_catalog_repository=fixture.category_catalog_repository,
        store_operations=fixture.store_operations,
        clock=fixture.clock,
    )


def _command(
    fixture: MedicationHistoryFixture,
    record: MedicationHistoryRecord,
    *,
    target: str,
    operation: str = "replace",
    value: object = _MISSING,
    reason: str = "原記録を確認して訂正した。",
) -> Any:
    command_type = getattr(_module(), "CorrectMedicationHistoryFactCommand", None)
    assert callable(command_type), "薬歴事実訂正 Command が必要"
    values: dict[str, object] = {
        "corporate_id": str(fixture.corporate_id.value),
        "record_id": str(record.id.value),
        "target": target,
        "operation": operation,
        "reason": reason,
    }
    if value is not _MISSING:
        values["value"] = value
    return command_type(**values)


async def _execute(
    fixture: MedicationHistoryFixture,
    record: MedicationHistoryRecord,
    *,
    target: str,
    operation: str = "replace",
    value: object = _MISSING,
    actor: ActorContext | None = None,
    unit_of_work: UnitOfWork | None = None,
) -> Any:
    return await _use_case(fixture, actor=actor, unit_of_work=unit_of_work).execute(
        _command(fixture, record, target=target, operation=operation, value=value)
    )


async def _stored_record(
    fixture: MedicationHistoryFixture,
    *,
    profile_updates: ProfileUpdateIntents | None = None,
    source_system: str | None = None,
    additional_notes: tuple[CategorizedNote, ...] = (),
    event_id: EventId | None = None,
) -> MedicationHistoryRecord:
    record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.counselor_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
            event_id=event_id,
            profile_updates=profile_updates,
            additional_notes=additional_notes,
        )
    )
    if source_system is not None:
        record = replace(
            record,
            source_system=MedicationHistorySourceSystem(source_system),
            imported_at=MedicationHistoryImportTimestamp(
                datetime(2026, 8, 23, 3, tzinfo=UTC)
            ),
        )
    await fixture.record_repository.save(record)
    await fixture.profile_repository.save(
        PatientMedicalProfile.rebuild_from(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            records=(record,),
        )
    )
    fixture.clock.advance(timedelta(days=3))
    return record


def _profile_content(profile: PatientMedicalProfile) -> tuple[object, ...]:
    return (
        profile.corporate_id,
        profile.patient_id,
        profile.allergies,
        profile.adverse_reactions,
        profile.medical_conditions,
        profile.concurrent_medications,
        profile.lifestyle,
        profile.generic_preference,
        profile.family_pharmacist,
    )


async def test_tc02_取込由来の訂正はReception原本を変えない() -> None:
    fixture = create_fixture()
    source_command = create_nsips_start_command(fixture)
    record = await _stored_record(
        fixture,
        source_system="NSIPS",
        event_id=EventId.parse(source_command.event_id),
    )
    reception_before = dict(fixture.reception_repository.items)
    assert reception_before

    await _execute(fixture, record, target="source_system", value="MANUAL")
    stored = fixture.record_repository.items[record.id]

    assert stored.source_system == record.source_system
    assert stored.imported_at == record.imported_at
    assert stored.effective_facts.source_system is not None
    assert stored.effective_facts.source_system.value == "MANUAL"
    assert fixture.reception_repository.items == reception_before


async def test_tc25_過去のIntent訂正後も全店舗の再生と保存済み投影が一致する() -> None:
    fixture = create_fixture()
    original = await _stored_record(
        fixture,
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),)),
    )
    other_store_id = StoreId.generate()
    fixture.store_reference.register(
        corporate_id=fixture.corporate_id, store_id=other_store_id
    )
    assert original.counseled_at is not None
    later = create_independent_follow_up_record(
        original,
        store_id=other_store_id,
        counseled_at=original.counseled_at.value + timedelta(days=1),
        finalized=True,
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent("卵白"),)
        ),
    )
    await fixture.record_repository.save(later)
    element_id = _element_id(original, "profile_updates.new_allergies", 0)
    initial_profile = next(iter(fixture.profile_repository.items.values()))

    await _execute(fixture, original, target=element_id, operation="retract")
    records = tuple(fixture.record_repository.items.values())
    rebuilt = PatientMedicalProfile.rebuild_from(
        corporate_id=fixture.corporate_id,
        patient_id=fixture.patient_id,
        records=records,
    )
    saved = next(iter(fixture.profile_repository.items.values()))

    assert saved.id == initial_profile.id
    assert _profile_content(saved) == _profile_content(rebuilt)
    assert len(saved.allergies) == 1
    assert saved.allergies[0].provenance.source_record_id == later.id


async def test_tc29_訂正者と時刻はActorとClockから決まる() -> None:
    fixture = create_fixture()
    record = await _stored_record(fixture)
    expected_now = fixture.clock.now()

    await _execute(fixture, record, target="information_sheet_provided", value=True)
    stored = fixture.record_repository.items[record.id]
    event = stored.fact_corrections[-1]

    assert event.corrected_by == fixture.counselor_id
    assert event.recorded_at.value == expected_now
    assert stored.finalized_at == record.finalized_at
    assert stored.recorded_at == record.recorded_at


@pytest.mark.parametrize("staff_kind", ("unqualified", "missing", "foreign"))
async def test_tc30_訂正先の指導者は同法人の薬剤師に限る(
    staff_kind: str,
) -> None:
    fixture = create_fixture()
    record = await _stored_record(fixture)
    other_staff = StaffId.generate()
    if staff_kind == "unqualified":
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=other_staff,
            qualifications=StaffQualifications.empty(),
        )
    if staff_kind == "foreign":
        fixture.staff_qualification.register(
            corporate_id=CorporateId.generate(),
            staff_id=other_staff,
            qualifications=StaffQualifications.empty(),
        )
    expected = (
        CounselorQualificationError
        if staff_kind == "unqualified"
        else MedicationHistoryStaffNotFoundError
    )

    with pytest.raises(expected):
        await _execute(
            fixture,
            record,
            target="counselor_id",
            value=str(other_staff.value),
        )

    assert (
        fixture.record_repository.items[record.id].counselor_id == record.counselor_id
    )


@pytest.mark.parametrize("actor_kind", ("unresolved", "unqualified", "viewer"))
async def test_tc31_実行者の本人解決と薬剤師資格と権限を要求する(
    actor_kind: str,
) -> None:
    fixture = create_fixture()
    record = await _stored_record(fixture)
    actor = create_resolved_actor(
        staff_id=None if actor_kind == "unresolved" else StaffId.generate(),
        role=ActorRole.STORE_VIEWER
        if actor_kind == "viewer"
        else ActorRole.STORE_OPERATOR,
        corporate_id=fixture.corporate_id,
        store_ids=frozenset({fixture.store_id}),
    )
    if actor_kind == "viewer":
        actor = replace(actor, staff_id=fixture.counselor_id)
    if actor_kind == "unqualified" and actor.staff_id is not None:
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=actor.staff_id,
            qualifications=StaffQualifications.empty(),
        )

    expected_error = (
        CounselorQualificationError if actor_kind == "unqualified" else ApplicationError
    )
    with pytest.raises(expected_error):
        await _execute(
            fixture,
            record,
            target="information_sheet_provided",
            value=True,
            actor=actor,
        )

    assert (
        fixture.record_repository.items[record.id].information_sheet_provided is False
    )


async def test_tc33_無効法人では訂正を保存しない() -> None:
    fixture = create_fixture()
    record = await _stored_record(fixture)
    fixture.corporate_repository.set_inactive(fixture.corporate_id)

    with pytest.raises(CorporateInactiveError):
        await _execute(fixture, record, target="information_sheet_provided", value=True)

    assert fixture.record_repository.items[record.id].fact_corrections == ()


@dataclass
class _InactiveUnitOfWork:
    """開始前・終了後の業務更新を拒否するテスト境界。"""

    phase: str
    ensure_calls: int = 0

    def ensure_active(self) -> None:
        self.ensure_calls += 1
        raise RuntimeError(f"Unit of Work は {self.phase} です。")


@pytest.mark.parametrize("phase", ("開始前", "終了後"))
async def test_tc34_開始していないUnitOfWorkでは訂正しない(phase: str) -> None:
    fixture = create_fixture()
    record = await _stored_record(fixture)
    work = _InactiveUnitOfWork(phase=phase)

    with pytest.raises(RuntimeError, match="Unit of Work"):
        await _execute(
            fixture,
            record,
            target="information_sheet_provided",
            value=True,
            unit_of_work=work,
        )

    assert work.ensure_calls == 1
    assert fixture.record_repository.items[record.id].fact_corrections == ()


async def test_tc35_薬歴を先に保存して同じ投影IDを維持する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = create_fixture()
    record = await _stored_record(
        fixture,
        profile_updates=ProfileUpdateIntents(new_allergies=(create_allergy_intent(),)),
    )
    original_profile = next(iter(fixture.profile_repository.items.values()))
    order: list[str] = []
    record_save = fixture.record_repository.save
    profile_save = fixture.profile_repository.save

    async def save_record(value: MedicationHistoryRecord) -> None:
        order.append("record")
        await record_save(value)

    async def save_profile(value: PatientMedicalProfile) -> None:
        order.append("profile")
        await profile_save(value)

    monkeypatch.setattr(fixture.record_repository, "save", save_record)
    monkeypatch.setattr(fixture.profile_repository, "save", save_profile)

    await _execute(fixture, record, target="information_sheet_provided", value=True)

    saved = next(iter(fixture.profile_repository.items.values()))
    assert order == ["record", "profile"]
    assert saved.id == original_profile.id


async def test_tc44_法人必須区分を欠く訂正だけを拒否する() -> None:
    fixture = create_fixture()
    major = MajorCategoryCode("clinical")
    medium = MediumCategoryCode("counseling")
    note = CategorizedNote(
        major_category_code=major,
        medium_category_code=medium,
        text=CounselingNote("服薬状況を確認した。"),
    )
    record = await _stored_record(fixture, additional_notes=(note,))
    catalog = MedicationHistoryCategoryCatalog(
        id=CategoryCatalogId.generate(),
        corporate_id=fixture.corporate_id,
        major_categories=(
            MajorCategoryDefinition(
                code=major,
                name=MajorCategoryName("薬学的管理"),
                display_order=1,
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=medium,
                major_category_code=major,
                name=MediumCategoryName("服薬状況"),
                display_order=1,
                is_required=True,
            ),
        ),
    )
    await fixture.category_catalog_repository.save(catalog)
    element_id = _element_id(record, "additional_notes", 0)

    with pytest.raises(RequiredCategoryMissingError):
        await _execute(fixture, record, target=element_id, operation="retract")
    assert fixture.record_repository.items[record.id].additional_notes == (note,)

    valid_note = replace(note, text=CounselingNote("本人の申告を再確認した。"))
    await _execute(fixture, record, target=element_id, value=valid_note)
    stored = fixture.record_repository.items[record.id]
    assert stored.additional_notes == (note,)
    assert stored.effective_facts.additional_notes == (valid_note,)
