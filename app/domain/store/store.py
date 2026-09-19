from dataclasses import dataclass, replace
from datetime import date, datetime, time
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.store.business_hours import BusinessHours, StoreOpeningState
from app.domain.store.lifecycle import (
    StoreStateConflictError,
    StoreStatus,
    StoreStatusChange,
    StoreStatusReason,
)
from app.domain.store.primitives import (
    ContactInfo,
    InsurancePharmacyNumber,
    StoreAddress,
    StoreCode,
    StoreId,
    StoreNames,
)


# 💡 修正1: frozen=True を追加
@dataclass(frozen=True, eq=False, kw_only=True)
class Store(AggregateRoot[StoreId]):
    """店舗（薬局）エンティティ（集約ルート）"""

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
        person_id: AccountPersonId,
        account_id: UserAccountId,
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
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
        return replace(
            self,
            status=StoreStatus.SUSPENDED,
            status_history=(*self.status_history, change),
        )

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        names: StoreNames,
        address: StoreAddress,
        contact_info: ContactInfo,
        code: StoreCode | None = None,
        insurance_pharmacy_number: InsurancePharmacyNumber | None = None,
    ) -> Self:
        """新規店舗のファクトリメソッド"""
        return cls(
            id=StoreId.generate(),
            corporate_id=corporate_id,
            code=code,
            names=names,
            address=address,
            contact_info=contact_info,
            insurance_pharmacy_number=insurance_pharmacy_number,
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
