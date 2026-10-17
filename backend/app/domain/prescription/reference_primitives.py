"""処方箋に記載された薬品情報の不変スナップショット。マスタの実装型は保持しない。"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString


class MedicineCodeType(StrEnum):
    """薬品コードの体系。

    JAHISの紙処方箋では6体系を使う一方、電子処方箋では使用可能な体系が
    異なる。電子処方箋との組み合わせ判定は、このコード体系ではなく
    ``Prescription`` が受領元形式と一緒に行う。
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


class MedicineCode(BaseNormalizedString):
    """薬品コード。

    桁数はコード体系ごとに異なる（レセプト電算・YJ・HOT・一般名）。電子処方箋の
    処方編・調剤編も薬品レコードを「薬品コード X 13 可変」と定めているため、
    ここでは固定桁数を課さない。コード体系ごとの妥当性は取り込み元で検証する。
    """


class MedicineName(BaseNormalizedString):
    """薬品名称。

    医薬品マスタの表示名だけでなく、未収載薬・OTC・健康食品の名称も表す。
    この値を持つことは医薬品マスタ行の存在を意味しない。
    """

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


class YjCode(BaseNormalizedString):
    """厚生労働省薬価基準収載医薬品コード（YJコード、12桁英数字）。"""

    def _normalize(self, value: str) -> str:
        if not isinstance(value, str):
            raise DomainValidationError("YJコードは文字列である必要があります。")
        nfkc = unicodedata.normalize("NFKC", value)
        return super()._normalize(nfkc).upper()

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("YJコードは空にできません。")
        if not re.fullmatch(r"^[0-9A-Z]{12}$", self.value):
            raise DomainValidationError(
                f"YJコードは12桁の半角英数字である必要があります。指定された値: '{self.value}'"
            )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, YjCode):
            return NotImplemented
        return self.value < other.value
