"""MedicineCatalogコンテキストの識別子・マスタ属性プリミティブ。

**このコンテキストはテナント境界を持たない。** 薬価基準は国が定めるものであり、
法人ごとに内容が違わない。`corporate_id` を付けて法人ごとに複製すると、
改定のたびに全テナント分を更新する羽目になる。

「自局で採用している薬か」「院内製剤か」はテナントごとの判断だが、それは
別の集約（自局採用薬）の責務であり、ここには持たせない。
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from app.base.domain.primitives.primitives import BaseDate, EntityUUID


class MedicineCatalogEntryId(EntityUUID):
    """医薬品マスタ1行の一意識別子（UUIDv7）。

    ``MedicineIdentifier``（薬品コード）を同一性に使わない。同じ薬品コードでも
    収載期間の異なる行が複数存在しうるためで、コードを識別子にすると
    「いつ時点のマスタか」を表せなくなる。
    """

    identifier_name = "医薬品マスタ行ID"


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
