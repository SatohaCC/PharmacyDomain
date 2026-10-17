"""利用側が所有する不変の参照情報。元コンテキストの実装型は保持しない。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from app.domain.dispensing.reference_primitives import (
    DailyFrequency,
    DosageCode,
    DosageCodeType,
    DosageName,
    MedicineCode,
    MedicineCodeType,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject


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


@dataclass(frozen=True, kw_only=True)
class DosageInstruction(ValueObject):
    """用法（JAHIS レコードNo.111 / 処方編 用法レコード）。

    調剤側でも同じ値を持つ。減数調剤は「用法及び用量の変更は行わずに投与日数等を
    減らす調剤」なので、調剤結果の用法は処方箋の用法と一致する。
    """

    code_type: DosageCodeType
    name: DosageName
    code: DosageCode | None = None
    daily_frequency: DailyFrequency | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code_type": "用法コード種別",
        "name": "用法名称",
        "code": "用法コード",
        "daily_frequency": "1日回数",
    }

    def validate(self) -> None:
        """コード種別とコードの有無の整合性を検証する。

        ``MedicineIdentifier`` と同じ形の検証であり、コンテキスト固有の業務例外
        ではなく ``DomainValidationError`` を送出する（Shared Kernel は各
        コンテキストの例外型を知らない）。
        """
        if self.code_type is DosageCodeType.NONE:
            if self.code is not None:
                raise DomainValidationError(
                    "用法コード種別が「コードなし」のときは用法コードを指定できません。"
                )
            return
        if self.code is None:
            raise DomainValidationError(
                f"用法コード種別が「{self.code_type.label}」のときは"
                "用法コードが必要です。"
            )
