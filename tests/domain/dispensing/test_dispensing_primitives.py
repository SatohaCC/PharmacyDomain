"""調剤プリミティブのテスト。

規格・通知に根拠のある値（分割理由ごとの回数上限、調剤終了区分のコード）を
固定する。ここが緩むと、返戻される記録が構築できてしまう。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.domain.dispensing import (
    AuditTimestamp,
    DispensingCompletionType,
    DispensingIteration,
    DispensingProcessStatus,
    DispensingSplitReason,
    DispensingTimestamp,
    PreparationMethod,
    QuantityAdjustmentReason,
    SubstitutionCategory,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.foundation.exceptions import DomainValidationError


class Test分割理由と調剤回数:
    """保険調剤の理解のために（令和8年度）の注9・注10・注11。"""

    def test_後発医薬品の試用は_2回目までしか成立しない(self) -> None:
        """注10 は「2回目の調剤を行った場合に限り」＝実質2分割。"""
        # Arrange
        reason = DispensingSplitReason.GENERIC_TRIAL

        # Act / Assert
        assert reason.allows_iteration(1)
        assert reason.allows_iteration(2)
        assert not reason.allows_iteration(3)

    def test_医師の分割指示は_3回目まで成立する(self) -> None:
        """注11 は3分割まで。"""
        # Arrange
        reason = DispensingSplitReason.PRESCRIBER_INSTRUCTED

        # Act / Assert
        assert reason.allows_iteration(3)
        assert not reason.allows_iteration(4)

    def test_長期保存の困難性等は_上限が無い(self) -> None:
        """注9 は回数上限の定めが無い。上限を型に持たせると表現できなくなる。"""
        # Arrange
        reason = DispensingSplitReason.LONG_TERM_STORAGE

        # Act / Assert
        assert reason.iteration_range == (2, None)
        assert reason.allows_iteration(2)
        assert reason.allows_iteration(99)

    def test_長期保存の困難性等は_1回目には成立しない(self) -> None:
        """注9 は2回目以降の分割調剤に対する規定。"""
        # Arrange / Act / Assert
        assert not DispensingSplitReason.LONG_TERM_STORAGE.allows_iteration(1)

    def test_分割理由には_調剤基本料の注番号が対応する(self) -> None:
        # Arrange / Act / Assert
        assert DispensingSplitReason.LONG_TERM_STORAGE.note_number == "9"
        assert DispensingSplitReason.GENERIC_TRIAL.note_number == "10"
        assert DispensingSplitReason.PRESCRIBER_INSTRUCTED.note_number == "11"

    def test_全ての分割理由に_回数範囲が定義されている(self) -> None:
        """読み込み時チェックが効いていることを、利用側からも確かめる。"""
        # Arrange / Act / Assert
        for reason in DispensingSplitReason:
            minimum, maximum = reason.iteration_range
            assert minimum >= 1
            assert maximum is None or maximum >= minimum
            assert reason.allowed_range_label

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
        assert len(values) == 3

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
