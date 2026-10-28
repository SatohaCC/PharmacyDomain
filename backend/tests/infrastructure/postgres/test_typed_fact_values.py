"""型付き訂正履歴の保存・復元内容を検証する。"""

from datetime import UTC, datetime

import pytest

from app.domain.medication_history.entities import (
    MedicationHistoryFactCorrection,
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    CounselingMethod,
    MedicationHistoryReviewResult,
    MedicationHistorySourceSystem,
)
from app.domain.staff.identifiers import StaffId
from app.infrastructure.postgres.codec import decode_aggregate, encode_aggregate
from tests.factories.medication_history_factory import (
    create_record,
    finalize_record_with_review,
)


def test_保存復元_型付き訂正値と監査内容を維持する() -> None:
    # Arrange
    record = finalize_record_with_review(create_record())
    corrected = record.correct_fact(
        target="information_sheet_provided",
        value=False,
        reason="テスト訂正理由",
        corrected_by=StaffId.generate(),
        recorded_at=datetime(2026, 10, 28, tzinfo=UTC),
    )

    # Act
    restored = decode_aggregate(encode_aggregate(corrected), MedicationHistoryRecord)

    # Assert
    expected = corrected.fact_corrections[0]
    actual = restored.fact_corrections[0]
    assert type(actual) is MedicationHistoryFactCorrection
    assert actual.id == expected.id
    assert actual.target == expected.target
    assert actual.field_name is expected.field_name
    assert actual.before == expected.before
    assert actual.after is False
    assert actual.reason == expected.reason
    assert actual.recorded_at == expected.recorded_at
    assert restored.effective_facts.information_sheet_provided is False


@pytest.mark.parametrize(
    ("target", "value"),
    [("review_result", value) for value in MedicationHistoryReviewResult]
    + [("method", value) for value in CounselingMethod]
    + [("source_system", MedicationHistorySourceSystem("テスト取得元"))],
)
def test_保存復元_訂正前後の業務型を別候補へ変換しない(
    target: str,
    value: MedicationHistoryReviewResult
    | CounselingMethod
    | MedicationHistorySourceSystem,
) -> None:
    # Arrange
    record = finalize_record_with_review(create_record())
    corrected = record.correct_fact(
        target=target,
        value=value,
        reason="テスト列挙値の訂正",
        corrected_by=StaffId.generate(),
        recorded_at=datetime(2026, 10, 28, tzinfo=UTC),
    )
    expected = corrected.fact_corrections[0]

    # Act
    restored = decode_aggregate(encode_aggregate(corrected), MedicationHistoryRecord)

    # Assert
    actual = restored.fact_corrections[0]
    assert type(actual.before) is type(expected.before)
    assert actual.before == expected.before
    assert type(actual.after) is type(value)
    assert actual.after == value
    assert getattr(restored.effective_facts, target) == value
