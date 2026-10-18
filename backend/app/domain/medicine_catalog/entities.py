"""medicine_catalogのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Self

from app.domain.foundation.entity import AggregateRoot
from app.domain.medicine_catalog.exceptions import MedicineCodeRequiredError
from app.domain.medicine_catalog.identifiers import MedicineCatalogEntryId
from app.domain.medicine_catalog.primitives import (
    GenericCategory,
    MedicineCatalogVersion,
    MedicineDosageForm,
    MedicineName,
    MedicineUnit,
    NarcoticCategory,
)
from app.domain.medicine_catalog.value_objects import (
    MedicineEffectivePeriod,
    MedicineIdentifier,
)


@dataclass(frozen=True, eq=False, kw_only=True)
class Medicine(AggregateRoot[MedicineCatalogEntryId]):
    """薬価基準収載品目1件（ある収載期間における姿）。

    保持するのは**マスタの生の事実**だけである。「リフィル不可の貼付剤か」の
    ような判定は、薬価基準ではなくリフィルの規則が定める組み合わせなので、
    ここではなく利用側（Composition のアダプタ）が導出する。
    生の事実だけを持つことで、Dispensing や請求算定側が別の導出を必要としても
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
