"""訂正値の型と保存・復元後の内容を検証する。"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.entities import MedicationHistoryFactCorrection
from app.domain.medication_history.identifiers import FactRecordId
from app.domain.medication_history.primitives import (
    FactCorrectionOperation,
    FactCorrectionReason,
    FactCorrectionTimestamp,
    FactFieldName,
    FactTarget,
)
from app.domain.medication_history.value_objects import FactValue
from app.domain.staff.identifiers import StaffId


def _correction() -> MedicationHistoryFactCorrection:
    return MedicationHistoryFactCorrection(
        id=FactRecordId("テスト訂正"),
        target=FactTarget("information_sheet_provided"),
        field_name=FactFieldName.INFORMATION_SHEET_PROVIDED,
        operation=FactCorrectionOperation.REPLACE,
        before=None,
        after=True,
        reason=FactCorrectionReason("テスト訂正理由"),
        corrected_by=StaffId.generate(),
        recorded_at=FactCorrectionTimestamp(datetime(2026, 10, 28, tzinfo=UTC)),
    )


@pytest.mark.parametrize("invalid", [0, "テスト値", object()])
def test_訂正値_項目と異なる型なら構築を拒否する(invalid: object) -> None:
    # Arrange
    correction = _correction()

    # Act / Assert
    with pytest.raises(DomainValidationError):
        replace(correction, after=cast(FactValue, invalid))


def test_訂正値_対象項目と異なる宛先を拒否する() -> None:
    # Act / Assert
    with pytest.raises(DomainValidationError, match="一致しません"):
        replace(_correction(), target=FactTarget("method"))


def test_取消操作_訂正後の値を保持できない() -> None:
    # Act / Assert
    with pytest.raises(DomainValidationError, match="取消し"):
        replace(_correction(), operation=FactCorrectionOperation.RETRACT)
