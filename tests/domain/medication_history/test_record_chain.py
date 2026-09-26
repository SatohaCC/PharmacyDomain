"""独立したフォローアップ薬歴の種別と集約不変条件を検証する。"""

from dataclasses import replace

import pytest

from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyExistsError,
    MedicationHistoryDomainError,
    SoapContentRequiredError,
)
from app.domain.medication_history.primitives import (
    BillingAdditionCode,
    BillingAdditionName,
    CounselingNote,
    CounselingTimestamp,
    MajorCategoryCode,
    MedicationHistoryRecordKind,
    MedicationHistoryReviewResult,
    MediumCategoryCode,
)
from app.domain.medication_history.services import MedicationHistoryUniquenessService
from app.domain.medication_history.value_objects import (
    BillingAddition,
    CategorizedNote,
    SoapRecord,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_independent_follow_up_record,
    create_note,
    create_record,
    finalize_record_with_review,
)


def test_tc04_薬歴種別と参照元の組み合わせを検証する() -> None:
    """INITIALは参照なし、FOLLOW_UPは参照ありで、自身への参照は禁止する。"""
    source = create_record()

    with pytest.raises(MedicationHistoryDomainError):
        replace(
            source,
            record_kind=MedicationHistoryRecordKind.INITIAL,
            source_record_id=source.id,
        )
    with pytest.raises(MedicationHistoryDomainError):
        replace(
            source,
            record_kind=MedicationHistoryRecordKind.FOLLOW_UP,
            source_record_id=None,
        )
    with pytest.raises(MedicationHistoryDomainError):
        replace(
            source,
            record_kind=MedicationHistoryRecordKind.FOLLOW_UP,
            source_record_id=source.id,
        )


def test_tc05_独立フォローアップは初回調剤の加算を持てない() -> None:
    source = create_record()
    follow_up = create_independent_follow_up_record(source)
    addition = BillingAddition(
        code=BillingAdditionCode("test"), name=BillingAdditionName("初回加算")
    )

    with pytest.raises(MedicationHistoryDomainError):
        replace(follow_up, billing_additions=(addition,))


def test_tc06_S節だけの独立フォローアップをレビュー付きで確定できる() -> None:
    source = finalize_record_with_review(create_record())
    draft = replace(
        create_independent_follow_up_record(source),
        soap=SoapRecord(subjective=(create_note("服用状況を確認した。"),)),
        handbook_status=None,
        residual_drug=None,
        information_sheet_provided=None,
    )

    finalized = finalize_record_with_review(
        draft,
        review_result=MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS,
    )

    assert finalized.is_finalized
    assert finalized.record_kind is MedicationHistoryRecordKind.FOLLOW_UP
    assert finalized.source_record_id == source.id
    assert len(finalized.soap.subjective) == 1


def test_tc06_追加メモだけの独立フォローアップをレビュー付きで確定できる() -> None:
    source = finalize_record_with_review(create_record())
    draft = replace(
        create_independent_follow_up_record(source),
        soap=SoapRecord(),
        additional_notes=(
            CategorizedNote(
                major_category_code=MajorCategoryCode("follow_up"),
                medium_category_code=MediumCategoryCode("memo"),
                text=CounselingNote("服用状況を確認し、変化なし。"),
            ),
        ),
        handbook_status=None,
        residual_drug=None,
        information_sheet_provided=None,
    )

    finalized = finalize_record_with_review(
        draft,
        review_result=MedicationHistoryReviewResult.NO_ADDITIONAL_RECORDABLE_ITEMS,
    )

    assert finalized.is_finalized
    assert finalized.soap.is_empty
    assert finalized.additional_notes[0].has_content


def test_tc06_SOAPと追加メモが空なら独立フォローアップを確定できない() -> None:
    source = finalize_record_with_review(create_record())
    draft = replace(
        create_independent_follow_up_record(source),
        soap=SoapRecord(),
        handbook_status=None,
        residual_drug=None,
        information_sheet_provided=None,
    )

    with pytest.raises(SoapContentRequiredError):
        finalize_record_with_review(draft)


def test_tc07_同一調剤の一意性は初回薬歴だけに適用する() -> None:
    source = finalize_record_with_review(create_record())
    another_initial = finalize_record_with_review(
        replace(
            create_record(corporate_id=source.corporate_id),
            dispensing_id=source.dispensing_id,
        )
    )
    first_follow_up = create_independent_follow_up_record(source, finalized=True)
    second_follow_up = create_independent_follow_up_record(source, finalized=True)
    service = MedicationHistoryUniquenessService()

    with pytest.raises(MedicationHistoryAlreadyExistsError):
        service.ensure_no_conflict(another_initial, (source,))

    service.ensure_no_conflict(first_follow_up, (source,))
    service.ensure_no_conflict(second_follow_up, (source, first_follow_up))


def test_tc08_旧薬歴は種別指定が無ければ初回として扱う() -> None:
    record = create_record()

    assert record.record_kind is MedicationHistoryRecordKind.INITIAL
    assert record.source_record_id is None


def test_tc12_後続時刻は参照元より後の値として保持できる() -> None:
    source = finalize_record_with_review(create_record())
    follow_up = create_independent_follow_up_record(
        source, counseled_at=COUNSELED_AT.replace(day=25)
    )

    assert follow_up.counseled_at == CounselingTimestamp(COUNSELED_AT.replace(day=25))
    assert follow_up.counseled_at is not None
    assert source.counseled_at is not None
    assert follow_up.counseled_at.value > source.counseled_at.value
