"""医薬品マスタ集約。

薬価基準収載品目の**版付きの参照データ**であり、状態変更コマンドを持たない。
誰もこのシステムで医薬品を作らず・編集しない。外部（厚労省の薬価基準、
MEDIS の HOT コードマスタ等）から取り込む対象である。

そのため ``change_*`` メソッドは無い。訂正は取り込み直しであり、
新しい収載期間の行として積む。

**テナント境界を持たない。** 薬価基準は国が定めるので法人ごとに違わない
（``primitives.py`` の冒頭を参照）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import ClassVar, Self

from app.base.domain.entity import AggregateRoot
from app.base.domain.medicine import MedicineIdentifier, MedicineName, MedicineUnit
from app.base.domain.value_object import ValueObject
from app.domain.medicine_catalog.exceptions import (
    MedicineCodeRequiredError,
    MedicineEffectivePeriodInvertedError,
)
from app.domain.medicine_catalog.primitives import (
    GenericCategory,
    MedicineCatalogEntryId,
    MedicineCatalogVersion,
    MedicineDosageForm,
    MedicineListedOn,
    MedicineWithdrawnOn,
    NarcoticCategory,
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


@dataclass(frozen=True, eq=False, kw_only=True)
class Medicine(AggregateRoot[MedicineCatalogEntryId]):
    """薬価基準収載品目1件（ある収載期間における姿）。

    保持するのは**マスタの生の事実**だけである。「リフィル不可の貼付剤か」の
    ような判定は、薬価基準ではなくリフィルの規則が定める組み合わせなので、
    ここではなく利用側（Composition のアダプタ）が導出する。
    生の事実だけを持つことで、Dispensing や Claim が別の導出を必要としても
    このマスタを作り直さずに済む。
    """

    id: MedicineCatalogEntryId
    identifier: MedicineIdentifier
    name: MedicineName
    unit: MedicineUnit
    effective_period: MedicineEffectivePeriod
    catalog_version: MedicineCatalogVersion
    dosage_form: MedicineDosageForm
    narcotic_category: NarcoticCategory = NarcoticCategory.NONE
    generic_category: GenericCategory = GenericCategory.OTHER
    #: 投与量（投薬期間）に上限が定められている医薬品か。
    #: リフィル処方箋による調剤ができない医薬品の一方の柱。
    has_dosage_limit: bool = False
    #: 鎮痛・消炎に係る効能及び効果を有するか（貼付剤のリフィル判定に使う）。
    is_analgesic_antiinflammatory: bool = False
    #: 専ら皮膚疾患に用いるものか（同上。該当すると貼付剤の除外から外れる）。
    is_dermatological: bool = False

    def validate(self) -> None:
        """マスタ行が単独で判定できる不変条件を検証する。

        期間の整合は ``MedicineEffectivePeriod`` が構築時に見ている。同一薬品
        コードの期間が重ならないことは他の行を見ないと判定できないので、
        ``MedicineEffectivePeriodConflictService`` と Repository契約が担う。
        """
        self._ensure_has_code()

    def _ensure_has_code(self) -> None:
        """薬品コードを持つことを検証する。

        マスタは薬品コードで引くためにある。「コードなし」の行を登録すると
        二度と引けない行が積み上がる。
        """
        if self.identifier.code is None:
            raise MedicineCodeRequiredError()

    # ------------------------------------------------------------------
    # 導出プロパティ
    # ------------------------------------------------------------------

    def is_effective_on(self, target_date: date) -> bool:
        """指定日にこの行が有効かを返す。

        適用日を引数で受け取る全域関数にする。麻薬指定も経過措置も時点で
        変わるので、``date.today()`` を暗黙に使うと過去の調剤を誤判定する。
        """
        return self.effective_period.includes(target_date)

    @property
    def is_narcotic(self) -> bool:
        """麻薬処方箋の必須3項目が課される薬品か。"""
        return self.narcotic_category.is_narcotic

    @property
    def is_refill_restricted_patch(self) -> bool:
        """リフィル処方箋による調剤ができない貼付剤か。

        保険調剤の理解のために（令和8年度）の定義「貼付剤（鎮痛・消炎に係る
        効能及び効果を有するものであって、麻薬若しくは向精神薬であるもの又は
        専ら皮膚疾患に用いるものを除いたもの）」をそのまま組み合わせる。

        導出をここに置くのは、材料（剤形・効能・麻薬区分・皮膚疾患用）が
        すべてこの行の中にあり、外から値を渡す余地が無いからである。
        利用側は結果だけを受け取る。
        """
        if not self.dosage_form.is_patch:
            return False
        if not self.is_analgesic_antiinflammatory:
            return False
        if self.narcotic_category.excludes_refill_patch:
            return False
        return not self.is_dermatological

    @property
    def forbids_refill(self) -> bool:
        """リフィル処方箋による調剤ができない薬品か。"""
        return self.has_dosage_limit or self.is_refill_restricted_patch

    # ------------------------------------------------------------------
    # ファクトリ
    # ------------------------------------------------------------------

    @classmethod
    def register(
        cls,
        *,
        identifier: MedicineIdentifier,
        name: MedicineName,
        unit: MedicineUnit,
        effective_period: MedicineEffectivePeriod,
        catalog_version: MedicineCatalogVersion,
        dosage_form: MedicineDosageForm,
        narcotic_category: NarcoticCategory = NarcoticCategory.NONE,
        generic_category: GenericCategory = GenericCategory.OTHER,
        has_dosage_limit: bool = False,
        is_analgesic_antiinflammatory: bool = False,
        is_dermatological: bool = False,
    ) -> Self:
        """マスタ行を1件取り込む。"""
        return cls(
            id=MedicineCatalogEntryId.generate(),
            identifier=identifier,
            name=name,
            unit=unit,
            effective_period=effective_period,
            catalog_version=catalog_version,
            dosage_form=dosage_form,
            narcotic_category=narcotic_category,
            generic_category=generic_category,
            has_dosage_limit=has_dosage_limit,
            is_analgesic_antiinflammatory=is_analgesic_antiinflammatory,
            is_dermatological=is_dermatological,
        )
