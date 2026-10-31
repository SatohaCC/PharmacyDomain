"""Applicationのreferencesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.value_objects import (
    PharmacistQualification,
    PrescriptionSource,
)
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.shared.actor import AccountPersonId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class DispensingPolicySnapshot:
    """店舗の実効調剤ポリシーのスナップショット。"""

    require_prescription_audit: bool = False
    prohibit_self_verification: bool = False


class DispensingPolicyBoundary(Protocol):
    """調剤操作時に店舗の実効ポリシーを取得する境界。"""

    async def get_effective_policy(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> DispensingPolicySnapshot:
        """店舗の実効調剤ポリシーを取得する。"""
        ...


class StaffPersonBoundary(Protocol):
    """スタッフに対応する自然人を引く境界。"""

    async def person_of(
        self, corporate_id: CorporateId, staff_id: StaffId
    ) -> AccountPersonId | None:
        """固定済みの本人を返す。未固定・他法人・未存在は None で隠す。"""
        ...


class StoreReferenceBoundary(Protocol):
    """店舗集約を保持せず、店舗の法人境界だけを確認する境界。"""

    async def require_exists(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> None:
        """指定法人に店舗が存在することを確認する。

        Raises:
            DispensingStoreNotFoundError: 未存在または別法人の店舗である場合。
                他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...

    async def require_licensed(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        business_on: date,
        has_narcotics: bool = False,
    ) -> None:
        """店舗の許認可（薬局開設許可・麻薬小売業者免許）を確認する。

        Raises:
            DispensingStoreNotFoundError: 未存在または別法人の店舗である場合。
            PharmacyLicenseRequiredConflictError: 薬局開設許可が未登録または期間外の場合。
            NarcoticsLicenseRequiredConflictError: 麻薬調剤で麻薬免許が未登録または期間外の場合。
        """
        ...


class PrescriptionReferenceBoundary(Protocol):
    """調剤の判定に必要な処方原本の固定値を取り出す境界。"""

    async def get_or_raise(
        self, *, corporate_id: CorporateId, prescription_id: PrescriptionId
    ) -> PrescriptionSource:
        """指定法人の処方箋集約を取得する。

        Raises:
            DispensingPrescriptionNotFoundError: 未存在または別法人の処方箋で
                ある場合。他テナントの存在を隠すためAuthorizationErrorへ分けない。
        """
        ...


class PrescriptionCompletionBoundary(Protocol):
    """調剤の終了を処方箋側へ反映する境界。

    処方箋を調剤済へ進める契機は調剤終了区分であり（調剤編
    ``リフィル処方箋情報レコード(521)``）、その判断は調剤側にしか無い。
    **書き込みを伴う唯一の境界**である。
    """

    async def complete_dispensing(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
        dispensed_on: date | None = None,
    ) -> None:
        """処方箋を調剤済へ遷移させる。

        すでに調剤済の処方箋に対しては何もしない（冪等）。同じ処方箋を
        分割調剤の各回で完了しても、2回目以降が状態遷移エラーにならないため。

        Raises:
            DispensingPrescriptionNotFoundError: 未存在または別法人の処方箋で
                ある場合。
        """
        ...


class StaffQualificationBoundary(Protocol):
    """Staff集約を渡さず、保有資格だけを取り出す境界。

    薬剤師かどうかの**判定そのものは行わない**。判定は
    ``DispensingPharmacistService`` が担い、この境界は判定材料を運ぶ。
    境界側で判定させると、同じ規則が実装ごとに分岐する。
    """

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
        store_id: StoreId | None = None,
        as_of: date | None = None,
    ) -> PharmacistQualification:
        """指定法人に在籍するスタッフの保有資格を返す。

        Raises:
            DispensingStaffNotFoundError: 未存在または別法人のスタッフである場合。
                資格を持たないだけのスタッフはここでは例外にせず、空の
                ``PharmacistQualification`` を返す（存在はしているため）。
            AuthorizationError: スタッフが停止中、または指定店舗・業務日に有効な所属がない場合。
        """
        ...
