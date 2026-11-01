"""storeのエンティティと集約。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
from typing import Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.identity.identifiers import VendorOperatorId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.store.exceptions import (
    ManagerAssignmentStateConflictError,
    StoreStateConflictError,
)
from app.domain.store.identifiers import StoreId, StoreManagerAssignmentId
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    ManagerAssignmentStatus,
    StoreCode,
    StoreOpeningState,
    StoreStatus,
    StoreStatusReason,
)
from app.domain.store.value_objects import (
    BusinessHours,
    ContactInfo,
    ManagerAssignmentPeriod,
    PharmacyCertifications,
    PublicExpenseDesignations,
    StoreAddress,
    StoreLicenses,
    StoreNames,
    StorePolicy,
    StoreStatusChange,
)


@dataclass(frozen=True, eq=False, kw_only=True)
class StoreManagerAssignment(AggregateRoot[StoreManagerAssignmentId]):
    """店舗と人員をIDで結ぶ期間付き任命。"""

    id: StoreManagerAssignmentId
    corporate_id: CorporateId
    store_id: StoreId
    staff_id: StaffId
    #: そのスタッフに対応する自然人。専任義務（薬機法第7条第3項）は法人内の
    #: スタッフではなく人にかかるため、法人をまたいで競合を判定できる鍵が要る。
    #: スタッフと本人の対応は付け替えを封じてあるので、ここへ写しても後から
    #: 食い違わない。写しであることは複合外部キーがDB側でも保証する。
    person_id: AccountPersonId
    period: ManagerAssignmentPeriod
    status: ManagerAssignmentStatus = ManagerAssignmentStatus.CONFIRMED

    def is_effective_on(self, target_date: date) -> bool:
        """取消状態を含めて適用日に有効か判定する。"""
        return (
            self.status == ManagerAssignmentStatus.CONFIRMED
            and self.period.contains(target_date)
        )

    def cancel(self, *, applied_on: date) -> StoreManagerAssignment:
        """開始前の任命を取消し履歴を保持する。"""
        if applied_on >= self.period.starts_on:
            raise ManagerAssignmentStateConflictError(
                "開始済みの任命は取消ではなく期間を終了してください。"
            )
        return replace(self, status=ManagerAssignmentStatus.CANCELLED)

    def end(self, *, ends_on: date) -> StoreManagerAssignment:
        """任命の期間を終了する。"""
        if self.status != ManagerAssignmentStatus.CONFIRMED:
            raise ManagerAssignmentStateConflictError(
                "取消済みの任命は終了できません。"
            )
        if self.period.ends_on is not None and ends_on > self.period.ends_on:
            raise ManagerAssignmentStateConflictError(
                "任命終了では期間を延長できません。"
            )
        return replace(self, period=replace(self.period, ends_on=ends_on))


@dataclass(frozen=True, eq=False, kw_only=True)
class Store(AggregateRoot[StoreId]):
    """調剤薬局の店舗情報を管理するドメインエンティティ。"""

    id: StoreId
    #: 所属法人。集約をまたぐためIDのみを持ち、法人集約そのものは参照しない。
    #: 実在性は永続化層の外部キー制約で担保する。
    corporate_id: CorporateId
    names: StoreNames
    address: StoreAddress
    contact_info: ContactInfo
    # --- 任意項目（未定・未発行を許容） ---
    code: StoreCode | None = None
    insurance_pharmacy_number: InsurancePharmacyNumber | None = None
    status: StoreStatus = StoreStatus.ACTIVE
    status_history: tuple[StoreStatusChange, ...] = ()
    #: 開局時間。未登録を ``None`` で表し、「毎日定休」と区別する。既定を
    #: 「いつでも開いている」にも「いつも閉じている」にも倒さない。
    business_hours: BusinessHours | None = None
    #: 店舗の許認可（薬局開設許可・麻薬小売業者免許）。未登録を許容する。
    licenses: StoreLicenses | None = None
    #: 店舗ポリシー（None は法人値を採用）。
    policy: StorePolicy = field(default_factory=StorePolicy)
    #: 公費・指定医療機関情報一式。
    public_expense_designations: PublicExpenseDesignations = field(
        default_factory=PublicExpenseDesignations
    )
    #: 薬局機能認定・届出一式。
    certifications: PharmacyCertifications = field(
        default_factory=PharmacyCertifications
    )
    #: 医薬品安全管理責任者。
    safety_manager_id: StaffId | None = None

    def update_licenses(self, licenses: StoreLicenses) -> Self:
        """店舗の許認可情報を更新する。"""
        return replace(self, licenses=licenses)

    def update_public_expense_designations(
        self, designations: PublicExpenseDesignations
    ) -> Self:
        """店舗の公費・指定医療機関情報を更新する。"""
        return replace(self, public_expense_designations=designations)

    def update_certifications(self, certifications: PharmacyCertifications) -> Self:
        """店舗の薬局機能認定・届出情報を更新する。"""
        return replace(self, certifications=certifications)

    def appoint_safety_manager(self, staff_id: StaffId) -> Self:
        """医薬品安全管理責任者を指名する。"""
        return replace(self, safety_manager_id=staff_id)

    def remove_safety_manager(self) -> Self:
        """医薬品安全管理責任者を解任する。"""
        return replace(self, safety_manager_id=None)

    def change_policy(self, policy: StorePolicy) -> Self:
        """店舗ポリシー設定を変更する。"""
        return replace(self, policy=policy)

    def opening_state_at(self, *, on: date, at: time) -> StoreOpeningState:
        """その日時に開局しているか。

        店舗状態が有効でなければ、時間表に関わらず閉まっている。休止中の薬局へ
        患者を案内させないためで、判定を2箇所（状態と時間表）に分けると、
        呼び出し側がどちらかを見落とす。

        開局時間が未登録のときは ``UNKNOWN`` を返す。「登録が無いから開いて
        いる」に倒すと、案内や電話対応が実在しない時刻を伝える。判定できない
        ことを「該当しない」に倒さない。
        """
        if self.status != StoreStatus.ACTIVE:
            return StoreOpeningState.CLOSED
        if self.business_hours is None:
            return StoreOpeningState.UNKNOWN
        if self.business_hours.is_open_at(on=on, at=at):
            return StoreOpeningState.OPEN
        return StoreOpeningState.CLOSED

    def change_status(
        self,
        status: StoreStatus,
        *,
        reason: StoreStatusReason,
        person_id: AccountPersonId,
        account_id: UserAccountId,
        recorded_at: datetime,
    ) -> Self:
        """履歴を残して店舗の状態を変更する。"""
        if self.status == status:
            return self
        if self.status == StoreStatus.CLOSED:
            raise StoreStateConflictError("閉局済みの店舗の状態は変更できません。")
        change = StoreStatusChange(
            before=self.status,
            after=status,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
        return replace(
            self, status=status, status_history=(*self.status_history, change)
        )

    def revoke_closure(
        self,
        *,
        reason: StoreStatusReason,
        operator_id: VendorOperatorId | None = None,
        person_id: AccountPersonId | None = None,
        account_id: UserAccountId | None = None,
        recorded_at: datetime,
    ) -> Self:
        """誤って登録した閉局を取り消し、休止へ戻す。

        ``change_status`` とは別の操作にする。閉局は行政への廃止届を伴う手続き
        であり、通常の状態遷移として往復させてよいものではない。取消は「その
        手続きが誤りだった」という訂正であって、営業の再開ではない。

        戻す先は有効ではなく休止である。閉局の時点で管理薬剤師の任命は終了して
        いるので、いきなり有効へ戻すと、取消の直後から受付だけが通って管理
        薬剤師のいない店舗で業務が始まる。再開は通常の状態変更で行う。

        任命は復元しない。閉局中にその薬剤師が別の店舗の管理薬剤師になっていた
        場合、復元すると期間が重なって専任義務に反する。取消のあとで任命し直す。
        """
        if self.status != StoreStatus.CLOSED:
            raise StoreStateConflictError(
                "閉局していない店舗に対して、閉局の取消はできません。"
            )
        change = StoreStatusChange(
            before=self.status,
            after=StoreStatus.SUSPENDED,
            reason=reason,
            operator_id=operator_id,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
        return replace(
            self,
            status=StoreStatus.SUSPENDED,
            status_history=(*self.status_history, change),
        )

    # ------------------------------------------------------------------
    # ドメインメソッド（状態変更）
    #
    # イミュータブル設計のため、自身の中身は書き換えず、
    # 変更された状態を持つ「新しい Store インスタンス」を返す。
    # ------------------------------------------------------------------

    def change_names(self, new_names: StoreNames) -> Self:
        """店舗名（一式）を変更する"""
        return replace(self, names=new_names)

    def change_address(self, new_address: StoreAddress) -> Self:
        """所在地情報を変更する"""
        return replace(self, address=new_address)

    def change_contact_info(self, new_contact_info: ContactInfo) -> Self:
        """連絡先情報（電話・FAX・メール）を変更する"""
        return replace(self, contact_info=new_contact_info)

    def change_code(self, new_code: StoreCode | None) -> Self:
        """店舗コードを変更または解除する"""
        return replace(self, code=new_code)

    def change_business_hours(self, new_hours: BusinessHours) -> Self:
        """開局時間をまとめて置き換える。

        曜日ごとの部分更新は受けない。週次の予定は全曜日が揃って初めて意味を
        持つので、1曜日だけ差し替えられると、残りの曜日がいつのものか分から
        なくなる。
        """
        return replace(self, business_hours=new_hours)

    def change_insurance_pharmacy_number(
        self, new_number: InsurancePharmacyNumber | None
    ) -> Self:
        """保険薬局指定番号（10桁）を更新または解除する"""
        return replace(self, insurance_pharmacy_number=new_number)
