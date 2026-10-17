"""MedicineCatalogコンテキストの薬品語彙・識別子・マスタ属性プリミティブ。

**このコンテキストはテナント境界を持たない。** 薬価基準は国が定めるものであり、
法人ごとに内容が違わない。`corporate_id` を付けて法人ごとに複製すると、
改定のたびに全テナント分を更新する羽目になる。

「自局で採用している薬か」「院内製剤か」はテナントごとの判断だが、それは
別の集約（自局採用薬）の責務であり、ここには持たせない。

薬品名称・単位は処方箋や薬歴にスナップショットとして現れる場合もあるが、
その値の語彙は薬品側に属する。これらの値をここから参照しても、医薬品マスタ行の
存在やコードとの対応を意味しない。未収載薬・OTC・健康食品も表せる。
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseDate, BaseNormalizedString


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


class MedicineListedOn(BaseDate):
    """薬価基準への収載日。この日から処方・調剤に使える。"""


class MedicineWithdrawnOn(BaseDate):
    """経過措置期限（または削除日）。**この日までは使える**（当日を含む）。

    ``None`` は「現に収載されており期限が定まっていない」を意味する。
    """


class NarcoticCategory(StrEnum):
    """麻薬及び向精神薬取締法による規制区分。

    リフィル適用除外の判定で「麻薬若しくは向精神薬であるもの」を除外するため、
    麻薬と向精神薬を1つの真偽値に潰さず区別して持つ。麻薬処方箋の必須3項目は
    麻薬にだけ課され、向精神薬には課されない。
    """

    NONE = "none"
    NARCOTIC = "narcotic"
    PSYCHOTROPIC = "psychotropic"
    STIMULANT_RAW_MATERIAL = "stimulant_raw_material"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.NONE: "該当なし",
            self.NARCOTIC: "麻薬",
            self.PSYCHOTROPIC: "向精神薬",
            self.STIMULANT_RAW_MATERIAL: "覚醒剤原料",
        }
        return labels[self]

    @property
    def is_narcotic(self) -> bool:
        """麻薬処方箋の必須3項目が課される区分か。"""
        return self is NarcoticCategory.NARCOTIC

    @property
    def excludes_refill_patch(self) -> bool:
        """貼付剤のリフィル適用除外から**さらに除外される**区分か。

        「貼付剤（……麻薬若しくは向精神薬であるもの……を除いたもの）」の
        括弧内に対応する。麻薬・向精神薬の貼付剤は「投与量に限度が定められて
        いる医薬品」として別途扱われる。
        """
        return self in (
            NarcoticCategory.NARCOTIC,
            NarcoticCategory.PSYCHOTROPIC,
        )


class MedicineDosageForm(StrEnum):
    """薬価基準上の剤形。

    処方箋の剤形区分（``DosageFormCategory``: 内服・頓服・外用…）とは別軸で、
    こちらは**薬品そのものの形**を表す。リフィル適用除外の「貼付剤」の判定に使う。
    """

    TABLET = "tablet"
    CAPSULE = "capsule"
    POWDER = "powder"
    LIQUID = "liquid"
    INJECTION = "injection"
    PATCH = "patch"
    OINTMENT = "ointment"
    EYE_DROP = "eye_drop"
    SUPPOSITORY = "suppository"
    OTHER = "other"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.TABLET: "錠剤",
            self.CAPSULE: "カプセル剤",
            self.POWDER: "散剤・顆粒剤",
            self.LIQUID: "液剤・シロップ剤",
            self.INJECTION: "注射剤",
            self.PATCH: "貼付剤",
            self.OINTMENT: "軟膏・クリーム剤",
            self.EYE_DROP: "点眼・点鼻剤",
            self.SUPPOSITORY: "坐剤",
            self.OTHER: "その他",
        }
        return labels[self]

    @property
    def is_patch(self) -> bool:
        """貼付剤か。"""
        return self is MedicineDosageForm.PATCH


class GenericCategory(StrEnum):
    """先発・後発の別。

    後発医薬品への変更調剤（``SubstitutionCategory.GENERIC_SUBSTITUTION``）が
    本当に後発品への変更かを確かめるために持つ。
    """

    BRAND = "brand"
    GENERIC = "generic"
    LONG_LISTED = "long_listed"
    OTHER = "other"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.BRAND: "先発医薬品",
            self.GENERIC: "後発医薬品",
            self.LONG_LISTED: "長期収載品",
            self.OTHER: "その他（局方品等）",
        }
        return labels[self]


class MedicineCatalogVersion(BaseDate):
    """このマスタ行が由来する薬価基準の版（告示日）。

    取り込み元のファイルがどの版かを残す。同じ薬品コードの行が複数あるとき、
    どの改定で入った行かを追えるようにする。
    """

    identifier_name: ClassVar[str] = "薬価基準の版"
