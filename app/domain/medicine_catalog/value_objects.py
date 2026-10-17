"""医薬品マスタを照合するコードの複合値。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.medicine_catalog.primitives import MedicineCode, MedicineCodeType


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
