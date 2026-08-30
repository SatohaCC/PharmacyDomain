"""処方・調剤・薬歴・医薬品マスタが共有する薬品語彙（Shared Kernel）。

ここに置く理由は「**所有者がいないから**」である。

``PatientId`` は Patient 集約の同一性なので、参照する側は所有コンテキストから
import するのが正しい。一方 ``MedicineCatalogEntryId`` は版付きマスタ行の
同一性であり、``MedicineName`` や ``MedicineIdentifier`` は処方・調剤・薬歴にも
現れる。マスタに存在しない他院処方やOTCも表すため、これらは特定集約の
同一性ではない。

このモジュールは各コンテキストへ依存せず、Domain基盤だけに依存する。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseNormalizedString,
    BasePositiveDecimal,
    BasePositiveInt,
)
from app.domain.foundation.value_object import ValueObject


class MedicineCodeType(StrEnum):
    """薬品コード種別。

    規格上の出典は2つあり、**使用可能な値の集合が異なる**。

    - JAHIS 院外処方箋２次元シンボル記録条件規約 Ver.1.11 レコードNo.201 備考欄
      （1:コードなし, 2:レセプト電算, 3:厚生省, 4:YJ, 6:HOT, 7:一般名）
    - 電子処方箋 記録条件仕様（処方編）Ver.2.4 別表15
      （2:レセプト電算, 4:YJ, 7:一般名のみ。1・5・8は「未使用」、3・6は「使用しない」）

    どちらで使える値かは :attr:`allowed_in_electronic_prescription` が持つ。
    紙の値集合をそのまま電子処方箋へ流すと、送信不能なコードを凍結できてしまう。
    """

    NONE = "none"
    RECEIPT = "receipt"
    MHLW = "mhlw"
    YJ = "yj"
    HOT = "hot"
    GENERIC = "generic"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {
            self.NONE: "1",
            self.RECEIPT: "2",
            self.MHLW: "3",
            self.YJ: "4",
            self.HOT: "6",
            self.GENERIC: "7",
        }
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.NONE: "コードなし",
            self.RECEIPT: "レセプト電算処理システム用コード",
            self.MHLW: "厚生省コード",
            self.YJ: "YJコード",
            self.HOT: "HOTコード",
            self.GENERIC: "一般名コード",
        }
        return labels[self]

    @property
    def allowed_in_electronic_prescription(self) -> bool:
        """電子処方箋（処方編 別表15）で使用できるコード種別か。"""
        return self in _ELECTRONIC_PRESCRIPTION_CODE_TYPES


_ELECTRONIC_PRESCRIPTION_CODE_TYPES = frozenset(
    {
        MedicineCodeType.RECEIPT,
        MedicineCodeType.YJ,
        MedicineCodeType.GENERIC,
    }
)


class DosageFormCategory(StrEnum):
    """剤形区分（処方）。

    出典: 電子処方箋（処方編）Ver.2.4 別表13 / JAHIS Ver.1.11 レコードNo.101 備考欄。
    両規格で値は一致する。
    """

    INTERNAL = "internal"
    PRN = "prn"
    TOPICAL = "topical"
    INTERNAL_DROPS = "internal_drops"
    INJECTION = "injection"
    SUPPLY = "supply"
    OTHER = "other"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {
            self.INTERNAL: "1",
            self.PRN: "2",
            self.TOPICAL: "3",
            self.INTERNAL_DROPS: "4",
            self.INJECTION: "5",
            self.SUPPLY: "6",
            self.OTHER: "9",
        }
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.INTERNAL: "内服",
            self.PRN: "頓服",
            self.TOPICAL: "外用",
            self.INTERNAL_DROPS: "内服滴剤",
            self.INJECTION: "注射",
            self.SUPPLY: "医療材料",
            self.OTHER: "不明",
        }
        return labels[self]

    @property
    def quantity_meaning(self) -> str:
        """調剤数量が何を表すか（JAHIS レコードNo.101 備考欄）。"""
        if self is DosageFormCategory.INTERNAL:
            return "投与日数"
        if self is DosageFormCategory.PRN:
            return "投与回数"
        return "投与日数または回数"


class MedicineCode(BaseNormalizedString):
    """薬品コード。

    桁数はコード体系ごとに異なる（レセプト電算・YJ・HOT・一般名）。電子処方箋の
    処方編・調剤編も薬品レコードを「薬品コード X 13 可変」と定めているため、
    ここでは固定桁数を課さない。コード体系ごとの妥当性は取り込み元で検証する。
    """


class MedicineName(BaseNormalizedString):
    """薬品名称。医薬品・OTC・健康食品のいずれにも使う。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 180:
            raise DomainValidationError("薬品名称は180文字以内で指定してください。")


class MedicineUnit(BaseNormalizedString):
    """薬品の単位名（錠、g、mL、包 等）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 20:
            raise DomainValidationError("単位名は20文字以内で指定してください。")


class DosageAmount(BasePositiveDecimal):
    """薬品の分量。

    内服は1日量、頓服は1回量、外用・材料は処方総量を表す（剤形区分で決まる）。
    整数部6桁・小数部5桁。``float`` は受け付けない（基底クラスの docstring を参照）。
    """

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "分量"


class SingleDoseAmount(BasePositiveDecimal):
    """1回あたりの服用量。

    出典: JAHIS レコードNo.241（1回服用量レコード。未出力可・薬品補足レコードで
    代用可）。``DosageAmount``（内服なら1日量）とは意味が異なるので別の型にする。
    """

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "1回服用量"


class ConversionFactor(BasePositiveDecimal):
    """単位変換係数。

    ``薬価収載単位用量 = 処方用量 × 単位変換係数``。
    処方箋表記単位が官報告示薬価収載単位と異なる場合に記録する
    （JAHIS レコードNo.211 単位変換レコード）。
    """

    max_integer_digits: ClassVar[int] = 6
    max_decimal_places: ClassVar[int] = 5
    quantity_name: ClassVar[str] = "単位変換係数"


class DispensingQuantity(BasePositiveInt):
    """調剤数量。

    剤形区分により意味が変わる（内服:投与日数 / 頓服:投与回数 / 以外:日数または回数）。
    薬品の用量に総量を記録する場合は 1 を記録する（JAHIS レコードNo.101 備考欄）。
    """

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("調剤数量は999以内で指定してください。")


class RpNumber(BasePositiveInt):
    """処方箋内の剤番号（RP番号）。1から連番。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("RP番号は999以内で指定してください。")


class MedicineLineNumber(BasePositiveInt):
    """RP内の薬品連番。1から連番。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("RP内連番は999以内で指定してください。")


@dataclass(frozen=True, kw_only=True)
class MedicineIdentifier(ValueObject):
    """薬品コード種別とコードを不可分に束ねる値オブジェクト。

    桁数がコード種別に依存するため ``MedicineCode`` 単独では自己検証できない
    （AGENTS.md「レセプト番号の桁数はプリミティブの不変条件」に対する例外の扱い）。
    種別ごとに7つの型へ分ける案は、明細のフィールド型が動的になるため採らない。
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
