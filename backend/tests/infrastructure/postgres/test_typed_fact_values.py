"""型付き訂正履歴の保存・復元内容を検証する。"""

from datetime import UTC, datetime

from app.domain.medication_history.entities import (
    MedicationHistoryFactCorrection,
    MedicationHistoryRecord,
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
