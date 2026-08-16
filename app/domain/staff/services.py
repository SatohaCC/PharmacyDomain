from dataclasses import replace
from datetime import date, timedelta

from app.domain.corporate.primitives import CorporateId
from app.domain.staff.exceptions import (
    AffiliationDateConflictError,
    ConcurrentStoreConflictError,
    InvalidCorporateAssignmentError,
    PrimaryAffiliationDuplicationError,
    StaffCodeAlreadyExistsError,
)
from app.domain.staff.primitives import (
    AffiliationPeriod,
    StaffCode,
    StaffId,
    StoreAffiliation,
)
from app.domain.staff.repository import StaffRepository
from app.domain.staff.staff import Staff
from app.domain.store.store import Store


class StaffCodeUniquenessService:
    """同一法人内のスタッフコードの重複を防ぐドメインサービス。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def ensure_code_is_unique(
        self,
        *,
        corporate_id: CorporateId,
        code: StaffCode,
        excluding_id: StaffId | None = None,
    ) -> None:
        """同一法人内でスタッフコードが重複していないことを検証する。"""
        is_exists = await self._repository.exists_by_code(
            corporate_id=corporate_id,
            code=code,
            excluding_id=excluding_id,
        )
        if is_exists:
            raise StaffCodeAlreadyExistsError(
                f"同一法人内にスタッフコード '{code.value}' は既に登録されています。"
            )


class StaffStoreAssignmentService:
    """スタッフの店舗配属・異動に関するドメインルールを調整する無状態ドメインサービス。

    .. note::
        配属・異動・兼務変更のドメイン操作は、必ず本ドメインサービスを経由すること。

        ``Staff`` エンティティ単体に直接店舗IDと法人IDを個別の引数として渡して更新を行おうとすると、
        他法人の店舗IDに自法人の法人IDを添えて渡された場合にエンティティ単体では実在関係を
        検証できず、他法人の店舗が誤って登録されてしまう脆弱性（抜け道）が生じる。

        本サービスでは、DBからロードされた不変の ``Store`` エンティティを受け取り、
        ``store.corporate_id`` と ``staff.corporate_id`` の一致を厳格に検証することで、
        法人境界の不変条件を確実に保護する。
    """

    def _ensure_same_corporate(self, staff: Staff, store: Store) -> None:
        """スタッフと店舗が同一法人に属しているか検証する。"""
        if store.corporate_id != staff.corporate_id:
            raise InvalidCorporateAssignmentError(
                "別法人の店舗を割り当てることはできません。"
            )

    def transfer_home_store(
        self, staff: Staff, store: Store, transfer_date: date
    ) -> Staff:
        """主所属店舗の異動を行う。"""
        self._ensure_same_corporate(staff, store)
        new_affiliations = list(staff.affiliations)

        # 異動日より未来に既に開始されている主所属予約が存在する場合は衝突エラー
        if any(
            affiliation.is_primary and affiliation.period.start_date > transfer_date
            for affiliation in new_affiliations
        ):
            raise AffiliationDateConflictError(
                "異動日より未来に既存の主所属履歴または予約が存在します。"
            )

        # 異動日現在の主所属は、異動日の前日で終了させる。
        active_primary_affiliations = [
            (index, affiliation)
            for index, affiliation in enumerate(new_affiliations)
            if affiliation.is_primary and affiliation.period.is_active_on(transfer_date)
        ]
        if len(active_primary_affiliations) > 1:
            raise PrimaryAffiliationDuplicationError(
                "同じ日付に主所属店舗を複数持てません。"
            )

        if active_primary_affiliations:
            index, current_affiliation = active_primary_affiliations[0]
            if transfer_date <= current_affiliation.period.start_date:
                raise AffiliationDateConflictError(
                    "異動日は現在の主所属開始日より後である必要があります。"
                )
            new_affiliations[index] = current_affiliation.close(
                end_date=transfer_date - timedelta(days=1)
            )

        new_affiliations.append(
            StoreAffiliation(
                store_id=store.id,
                period=AffiliationPeriod(start_date=transfer_date),
                is_primary=True,
            )
        )
        return replace(staff, affiliations=tuple(new_affiliations))

    def assign_home_store(self, staff: Staff, store: Store, start_date: date) -> Staff:
        """スタッフに初回の主所属店舗を割り当てる。"""
        return self.transfer_home_store(staff, store, start_date)

    def assign_concurrent_store(
        self, staff: Staff, store: Store, start_date: date
    ) -> Staff:
        """兼務店舗を追加する。"""
        self._ensure_same_corporate(staff, store)

        if staff.current_home_store_id(start_date) == store.id:
            raise ConcurrentStoreConflictError("主所属店舗は兼務店舗に追加できません。")

        if any(
            not affiliation.is_primary
            and affiliation.store_id == store.id
            and affiliation.period.is_active_on(start_date)
            for affiliation in staff.affiliations
        ):
            raise ConcurrentStoreConflictError("指定店舗は既に兼務店舗です。")

        new_affiliation = StoreAffiliation(
            store_id=store.id,
            period=AffiliationPeriod(start_date=start_date),
            is_primary=False,
        )
        return replace(
            staff,
            affiliations=(*staff.affiliations, new_affiliation),
        )

    def remove_concurrent_store(
        self, staff: Staff, store: Store, end_date: date
    ) -> Staff:
        """兼務店舗から外す。"""
        self._ensure_same_corporate(staff, store)
        new_affiliations = list(staff.affiliations)

        matching_affiliations = [
            (index, affiliation)
            for index, affiliation in enumerate(new_affiliations)
            if not affiliation.is_primary
            and affiliation.store_id == store.id
            and affiliation.period.is_active_on(end_date)
        ]
        if not matching_affiliations:
            raise ConcurrentStoreConflictError(
                "指定された店舗の有効な兼務所属履歴が見つかりません。"
            )

        index, current_affiliation = matching_affiliations[0]
        if end_date < current_affiliation.period.start_date:
            raise AffiliationDateConflictError(
                "兼務解除日は兼務開始日以降である必要があります。"
            )

        new_affiliations[index] = current_affiliation.close(end_date=end_date)
        return replace(staff, affiliations=tuple(new_affiliations))
