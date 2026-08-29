"""Prescription Applicationが依存する参照境界。

Prescription は他コンテキストの集約を保持しない。集約が単独で判定できない
不変条件（``okf/ddd/prescription.md`` §5 の #5 / #6 / #7 / #8）に必要な事実は、
ここで定義した Protocol を通じて **本物の値オブジェクト**として受け取り、
Domain Service へ渡す。

**Boundary は Application層に置く。** 仕様書は当初これを Domain層の
``reference.py`` に置く想定だったが、既存の Boundary（Coverage / Reception）は
すべて Application層にあり、Domain Service は本物のオブジェクトを引数で受け取る。
置き場所を混在させると「どちらに置くか」が規約になり、必ず片方へ倒れる。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Protocol

from app.base.domain.medicine import MedicineIdentifier, PublicExpenseBurden
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.value_objects import MedicineClassification
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.store.primitives import StoreId


class StoreReferenceBoundary(Protocol):
    """店舗集約を保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """指定法人に店舗が存在することを確認する。

        Raises:
            PrescriptionStoreNotFoundError: 未存在または別法人の店舗である場合。
                他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class PatientReferenceBoundary(Protocol):
    """患者集約を保持せず、患者の法人境界だけを確認する境界。"""

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> None:
        """指定法人に患者が存在することを確認する。

        Raises:
            PrescriptionPatientNotFoundError: 未存在または別法人の患者である場合。
                他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class StaffQualificationBoundary(Protocol):
    """Staff集約を渡さず、保有資格だけを取り出す境界。

    疑義照会の実施者が薬剤師かどうか（不変条件 #8）の**判定そのものは行わない**。
    判定は ``InquiryPharmacistService`` が担い、この境界は判定材料を運ぶ。
    境界側で判定させると、同じ規則が実装ごとに分岐する。
    """

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """指定法人に在籍するスタッフの保有資格を返す。

        Raises:
            PrescriptionPharmacistNotFoundError: 未存在または別法人のスタッフで
                ある場合。他テナントの存在を隠すためAuthorizationErrorへ分けない。
                資格を持たないだけのスタッフはここでは例外にせず、空の
                ``StaffQualifications`` を返す（存在はしているため）。
        """
        ...


class MedicineRestrictionBoundary(Protocol):
    """医薬品マスタの規制属性を引く境界。

    本システムに医薬品集約は存在せず、マスタは外部にある。実装先が無い間も
    ``MedicineClassification`` の各フラグが ``UNKNOWN`` を表せるため、
    Domain Service は「不明」を「該当しない」へ倒さずに拒否できる。
    """

    async def classify(
        self,
        *,
        identifiers: tuple[MedicineIdentifier, ...],
        as_of: date,
    ) -> Mapping[MedicineIdentifier, MedicineClassification]:
        """指定日時点での、薬品識別子ごとの規制属性を返す。

        **適用日を必ず受け取る。** 麻薬指定も経過措置期限も時点で変わるので、
        「今」で引くと過去の処方を誤判定する。呼び出し側は処方箋の交付日を渡す。

        **マスタに存在しない薬品は戻り値へ含めない。** 欠落は
        ``MedicineClassificationMissingError`` として Domain Service が拒否する。
        ここで「該当しない」既定値を埋めると、マスタ未登録の薬品について
        麻薬・リフィル適用除外の判定が静かに素通りする。
        判定不能を表したい場合は ``MedicineRestrictionFlag.UNKNOWN`` を返す。
        """
        ...


class PublicExpenseAvailabilityBoundary(Protocol):
    """受付で確定した資格選択に、どの公費枠が存在するかを引く境界。"""

    async def available_burden(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        coverage_selection_record_id: CoverageSelectionRecordId,
    ) -> PublicExpenseBurden:
        """資格選択履歴に存在する公費枠を、処方箋側の枠として返す。

        処方箋の公費枠（第一/第二/第三/特殊）と資格台帳の順位（第一〜第四）は
        別軸であり、その対応づけは実アダプタ（Composition）の責務とする。
        この境界は「処方箋側の枠のうちどれが裏付けられるか」だけを答える。
        表現できない枠は ``False`` を返すこと。``True`` を既定にすると、
        裏付けの無い公費負担が処方箋に固定されてしまう。

        Raises:
            PrescriptionCoverageSelectionNotFoundError: 履歴が存在しない、または
                法人・患者が異なる場合。他テナントの存在を隠すため404相当に揃える。
        """
        ...
