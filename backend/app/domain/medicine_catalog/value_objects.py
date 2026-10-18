"""medicine_catalogの複合値と参照スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.medicine_catalog.exceptions import MedicineEffectivePeriodInvertedError
from app.domain.medicine_catalog.primitives import (
    MedicineCode,
    MedicineCodeType,
    MedicineListedOn,
    MedicineWithdrawnOn,
)


@dataclass(frozen=True, kw_only=True)
class MedicineEffectivePeriod(ValueObject):
    """マスタ行が有効な期間。

    終了日を**含む**閉区間 ``[listed_on, withdrawn_on]`` とする。経過措置期限は
    「その日まで使える」を意味するため、資格の ``CoverageActivation``
    （``[activated_on, deactivated_on)`` の半開区間）とは区間の取り方が違う。
    同じ形にすると、期限当日の調剤を誤って弾く。
    """

    listed_on: MedicineListedOn
    withdrawn_on: MedicineWithdrawnOn | None = None

    _FIELD_LABELS: ClassVar[dict[str, str]] = {
        "listed_on": "収載日",
        "withdrawn_on": "経過措置期限",
    }

    def validate(self) -> None:
        """経過措置期限が収載日以降であることを検証する。"""
        if (
            self.withdrawn_on is not None
            and self.withdrawn_on.value < self.listed_on.value
        ):
            raise MedicineEffectivePeriodInvertedError()

    def includes(self, target_date: date) -> bool:
        """指定日にこの行が有効かを返す。"""
        if target_date < self.listed_on.value:
            return False
        return self.withdrawn_on is None or target_date <= self.withdrawn_on.value

    def overlaps(self, other: MedicineEffectivePeriod) -> bool:
        """別の期間と1日でも重なるかを返す。

        ``withdrawn_on`` が ``None`` の期間は未来側に終わりがないとみなす。
        """
        self_ends_first = (
            self.withdrawn_on is not None
            and self.withdrawn_on.value < other.listed_on.value
        )
        other_ends_first = (
            other.withdrawn_on is not None
            and other.withdrawn_on.value < self.listed_on.value
        )
        return not (self_ends_first or other_ends_first)


@dataclass(frozen=True, kw_only=True)
class MedicineIdentifier(ValueObject):
    """薬品コード種別とコードを不可分に束ねる値オブジェクト。

    桁数がコード種別に依存するため ``MedicineCode`` 単独では自己検証できない。
    種別ごとに型を分けると、処方箋明細のフィールド型が動的になるため採らない。
    コードなしの処方やマスタ未収載の持参薬も表せるため、医薬品マスタ行の存在を
    意味しない。ここで所有するのは、外部データ間で薬品を照合するコード語彙である。
    """

    code_type: MedicineCodeType
    code: MedicineCode | None = None

    _FIELD_LABELS: ClassVar[dict[str, str]] = {
        "code_type": "薬品コード種別",
        "code": "薬品コード",
    }

    def validate(self) -> None:
        """コード種別とコードの有無の整合性を検証する。"""
        if self.code_type is MedicineCodeType.NONE:
            if self.code is not None:
                raise DomainValidationError(
                    "薬品コード種別が「コードなし」のときは薬品コードを指定できません。"
                )
            return
        if self.code is None:
            raise DomainValidationError(
                f"薬品コード種別が「{self.code_type.label}」のときは"
                "薬品コードが必要です。"
            )
