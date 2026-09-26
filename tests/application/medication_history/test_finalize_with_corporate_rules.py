"""薬歴確定時の法人別記載区分ルール検証テスト。"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
    FinalizeMedicationHistoryUseCase,
)
from app.application.medication_history.inputs import (
    AddFollowUpCommand,
    LabeledNoteInput,
    SoapInput,
)
from app.domain.medication_history.category_catalog import (
    MedicationHistoryCategoryCatalog,
)
from app.domain.medication_history.exceptions import RequiredCategoryMissingError
from app.domain.medication_history.primitives import (
    CategoryCatalogId,
    MajorCategoryCode,
    MajorCategoryName,
    MediumCategoryCode,
    MediumCategoryName,
)
from app.domain.medication_history.value_objects import (
    MajorCategoryDefinition,
    MediumCategoryDefinition,
)
from tests.application.medication_history.helpers import (
    create_fixture,
    create_start_command,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork


@pytest.fixture
def catalog_repo() -> InMemoryMedicationHistoryCategoryCatalogRepository:
    return InMemoryMedicationHistoryCategoryCatalogRepository()


async def test_finalize_passes_when_corporate_required_categories_met(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
) -> None:
    """TC-APP-05: 法人ルールで必須の中区分（SとP）が記録されている場合、確定が成功すること。"""
    fixture = create_fixture()
    soap_code = MajorCategoryCode("soap")

    # 法人カタログで S と P を必須に設定
    catalog = MedicationHistoryCategoryCatalog(
        id=CategoryCatalogId.generate(),
        corporate_id=fixture.corporate_id,
        major_categories=(
            MajorCategoryDefinition(
                code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S"),
                display_order=1,
                is_required=True,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P"),
                display_order=2,
                is_required=True,
            ),
        ),
    )
    await catalog_repo.save(catalog)

    finalize_use_case = FinalizeMedicationHistoryUseCase(
        fixture.record_repository,
        fixture.profile_repository,
        fixture.start._corporate_access,
        NullUnitOfWork(),
        category_catalog_repository=catalog_repo,
        clock=fixture.clock,
    )

    # SとPを両方入力して下書き作成
    from tests.application.medication_history.helpers import create_start_command

    cmd = create_start_command(
        fixture,
        soap=SoapInput(
            subjective=(LabeledNoteInput(text="頭痛あり"),),
            plan=(LabeledNoteInput(text="頓服服用指導"),),
        ),
    )
    draft = await fixture.start.execute(cmd)

    # 確定実行 -> 成功
    finalized_dto = await finalize_use_case.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=draft.id,
            counseled_at=fixture.clock.now(),
            review_result="assessment_and_instruction_recorded",
        )
    )
    assert finalized_dto.status == "finalized"


async def test_finalize_fails_when_corporate_required_categories_missing(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
) -> None:
    """TC-APP-06: 法人ルールで必須の中区分（P）が不足している場合、確定が拒否されること。"""
    fixture = create_fixture()
    soap_code = MajorCategoryCode("soap")

    # 法人カタログで S と P を必須に設定
    catalog = MedicationHistoryCategoryCatalog(
        id=CategoryCatalogId.generate(),
        corporate_id=fixture.corporate_id,
        major_categories=(
            MajorCategoryDefinition(
                code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S"),
                display_order=1,
                is_required=True,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P（指導計画）"),
                display_order=2,
                is_required=True,
            ),
        ),
    )
    await catalog_repo.save(catalog)

    finalize_use_case = FinalizeMedicationHistoryUseCase(
        fixture.record_repository,
        fixture.profile_repository,
        fixture.start._corporate_access,
        NullUnitOfWork(),
        category_catalog_repository=catalog_repo,
        clock=fixture.clock,
    )

    from tests.application.medication_history.helpers import create_start_command

    # Sのみ入力し、Pは空で作成
    cmd = create_start_command(
        fixture,
        soap=SoapInput(
            subjective=(LabeledNoteInput(text="頭痛あり"),),
            plan=(),
        ),
    )
    draft = await fixture.start.execute(cmd)

    with pytest.raises(RequiredCategoryMissingError) as exc_info:
        await finalize_use_case.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=draft.id,
                counseled_at=fixture.clock.now(),
                review_result="assessment_and_instruction_recorded",
            )
        )
    assert "P（指導計画）" in str(exc_info.value)


async def test_tc29_法人の初回必須区分を_フォローアップには要求しない() -> None:
    """INITIAL は P を要求し、FOLLOW_UP は S だけでレビュー確定できる。"""
    fixture = create_fixture()
    soap_code = MajorCategoryCode("soap")
    await fixture.category_catalog_repository.save(
        MedicationHistoryCategoryCatalog(
            id=CategoryCatalogId.generate(),
            corporate_id=fixture.corporate_id,
            major_categories=(
                MajorCategoryDefinition(
                    code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
                ),
            ),
            medium_categories=(
                MediumCategoryDefinition(
                    code=MediumCategoryCode("s"),
                    major_category_code=soap_code,
                    name=MediumCategoryName("S"),
                    display_order=1,
                    is_required=True,
                ),
                MediumCategoryDefinition(
                    code=MediumCategoryCode("p"),
                    major_category_code=soap_code,
                    name=MediumCategoryName("P"),
                    display_order=2,
                    is_required=True,
                ),
            ),
        )
    )

    initial = await fixture.start.execute(create_start_command(fixture))
    await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=initial.id,
            review_result="assessment_and_instruction_recorded",
        )
    )
    followed_up_at = fixture.clock.now() + timedelta(days=3)
    follow_up = await fixture.add_follow_up.execute(
        AddFollowUpCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=initial.id,
            store_id=str(fixture.store_id.value),
            patient_id=str(fixture.patient_id.value),
            counselor_id=str(fixture.counselor_id.value),
            followed_up_at=followed_up_at,
            method="telephone",
            soap=SoapInput(subjective=(LabeledNoteInput(text="眠気は軽減した。"),)),
        )
    )
    fixture.clock.advance(followed_up_at - fixture.clock.now() + timedelta(hours=1))

    finalized = await fixture.finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=follow_up.id,
            review_result="no_additional_recordable_items",
        )
    )

    assert finalized.status == "finalized"
