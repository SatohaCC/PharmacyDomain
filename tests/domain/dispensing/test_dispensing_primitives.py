"""調剤プリミティブのテスト。

規格・通知に根拠のある値（分割理由ごとの回数上限、調剤終了区分のコード）を
固定する。ここが緩むと、返戻される記録が構築できてしまう。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.dispensing.primitives import (
    AuditTimestamp,
    DispensingCompletionType,
    DispensingIteration,
    DispensingProcessStatus,
    DispensingSplitReason,
    DispensingTimestamp,
    PreparationMethod,
    QuantityAdjustmentReason,
    SubstitutionCategory,
    TotalSplitCount,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.foundation.exceptions import DomainValidationError


class TestTotalSplitCount:
    """合計分割回数（2回以上の整数）。"""

    def test_2以上の整数で構築できる(self) -> None:
        # Arrange / Act
        actual2 = TotalSplitCount(2)
        actual3 = TotalSplitCount(3)
        actual10 = TotalSplitCount(10)

        # Assert
        assert actual2.value == 2
        assert actual3.value == 3
        assert actual10.value == 10

    def test_1以下は受け付けない(self) -> None:
        """分割調剤である以上、2分割以上が必要。"""
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="合計分割回数"):
            TotalSplitCount(1)

        with pytest.raises(DomainValidationError):
            TotalSplitCount(0)


class Test分割理由:
    """分割調剤の理由（注9・注10・注11）。"""

    def test_分割理由には_調剤基本料の注番号が対応する(self) -> None:
        # Arrange / Act / Assert
        assert DispensingSplitReason.LONG_TERM_STORAGE.note_number == "9"
        assert DispensingSplitReason.GENERIC_TRIAL.note_number == "10"
        assert DispensingSplitReason.PRESCRIBER_INSTRUCTED.note_number == "11"

    def test_表示名が取得できる(self) -> None:
        # Arrange / Act / Assert
        assert "長期保存" in DispensingSplitReason.LONG_TERM_STORAGE.label
        assert "後発医薬品" in DispensingSplitReason.GENERIC_TRIAL.label
        assert "分割指示" in DispensingSplitReason.PRESCRIBER_INSTRUCTED.label

    def test_リフィルは_分割理由に含まれない(self) -> None:
        """リフィルは処方箋側の指示であり、回数の根拠も算定方法も異なる。"""
        # Arrange / Act
        values = {reason.value for reason in DispensingSplitReason}

        # Assert
        assert "refill" not in values
        assert len(values) == 3


class Test調剤回数:
    """上限は型に持たせない。"""

    def test_1未満は_受け付けない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError):
            DispensingIteration(0)

    def test_上限を課さないので_大きな回数も構築できる(self) -> None:
        """注9 に回数上限の定めが無いため。"""
        # Arrange / Act
        actual = DispensingIteration(50)

        # Assert
        assert actual.value == 50


class Test調剤終了区分:
    """調剤編 リフィル処方箋情報レコード(521)。"""

    def test_終了は1_継続は2として記録する(self) -> None:
        # Arrange / Act / Assert
        assert DispensingCompletionType.COMPLETED.record_code == "1"
        assert DispensingCompletionType.CONTINUES.record_code == "2"

    def test_継続のときだけ_次回調剤予定日を要求する(self) -> None:
        # Arrange / Act / Assert
        assert DispensingCompletionType.CONTINUES.requires_next_date
        assert not DispensingCompletionType.COMPLETED.requires_next_date


class Test状態:
    """終端の定義。"""

    def test_交付済と中止が_終端になる(self) -> None:
        # Arrange / Act / Assert
        assert DispensingProcessStatus.COMPLETED.is_terminal
        assert DispensingProcessStatus.CANCELLED.is_terminal

    def test_調剤調製中と鑑査済は_終端ではない(self) -> None:
        # Arrange / Act / Assert
        assert not DispensingProcessStatus.IN_PROGRESS.is_terminal
        assert not DispensingProcessStatus.VERIFIED.is_terminal


class Test変更調剤の3軸:
    """3軸が別々の列挙であり、混ざっていないことを固定する。"""

    def test_代替調剤に_処方どおりを表す値は無い(self) -> None:
        """処方どおりは ``substitution is None``。値と ``None`` の二重表現を作らない。"""
        # Arrange / Act
        values = {item.value for item in SubstitutionCategory}

        # Assert
        assert "original_as_prescribed" not in values
        assert len(values) == 4

    def test_3軸の値集合が_互いに重ならない(self) -> None:
        """単一 enum へ戻す変更は、この重なりで検出される。"""
        # Arrange
        substitution = {item.value for item in SubstitutionCategory}
        adjustment = {item.value for item in QuantityAdjustmentReason}
        preparation = {item.value for item in PreparationMethod}

        # Act / Assert
        assert not substitution & adjustment
        assert not adjustment & preparation
        assert not preparation & substitution


class Test鑑査結果:
    """合格判定は列挙が持つ。"""

    def test_合格と不合格を判別できる(self) -> None:
        # Arrange / Act / Assert
        assert VerificationResult.PASSED.is_passed
        assert not VerificationResult.FAILED.is_passed


class Test監査時刻:
    """naive な日時は監査に使えないため拒否する。"""

    @pytest.mark.parametrize(
        "timestamp_type",
        [DispensingTimestamp, AuditTimestamp, VerificationTimestamp],
    )
    def test_タイムゾーンなしの日時は_拒否される(
        self, timestamp_type: type[DispensingTimestamp]
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="タイムゾーン"):
            timestamp_type(datetime(2026, 8, 24, 1, 30))  # noqa: DTZ001

    def test_タイムゾーン付きの日時は_UTCへ正規化される(self) -> None:
        # Arrange
        jst = datetime(2026, 8, 24, 10, 30, tzinfo=UTC).astimezone(UTC)

        # Act
        actual = DispensingTimestamp(jst)

        # Assert
        assert actual.value.tzinfo is UTC


class Test代替調剤種別:
    """疑義照会処方変更を含む代替調剤種別の定義。"""

    def test_疑義照会に基づく処方変更調剤の定義(self) -> None:
        """TC-CAT-01: SubstitutionCategory.INQUIRY_MODIFIED の値と日本語名称。"""
        # Arrange / Act / Assert
        assert SubstitutionCategory.INQUIRY_MODIFIED.value == "inquiry_modified"
        assert (
            SubstitutionCategory.INQUIRY_MODIFIED.label
            == "疑義照会に基づく処方変更調剤"
        )
