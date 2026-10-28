"""Applicationのorganization_snapshot_mappingを定義する。"""

from __future__ import annotations

from app.application.staff.interfaces.references import StaffStoreReference
from app.application.store.interfaces.references import ManagerStaffReference
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.value_objects import PharmacistProfile, StoreSource
from app.domain.store.entities import Store
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import StoreStatus
from app.domain.store.repositories import StoreRepository
from app.domain.store.value_objects import ManagerStaffAffiliation, ManagerStaffSource


def staff_store_source(value: Store) -> StoreSource:
    """配属判定へ店舗の同一性と閉局事実を渡す。"""
    return StoreSource(
        store_id=value.id,
        corporate_id=value.corporate_id,
        is_closed=value.status is StoreStatus.CLOSED,
    )


def manager_staff_source(value: Staff) -> ManagerStaffSource:
    """任命対象の資格と所属期間を固定する。"""
    return ManagerStaffSource(
        staff_id=value.id,
        corporate_id=value.corporate_id,
        staff_is_active=value.is_active,
        has_pharmacist=value.qualifications.has(PharmacistProfile),
        affiliations=tuple(
            ManagerStaffAffiliation(
                store_id=item.store_id,
                starts_on=item.period.start_date,
                ends_on=item.period.end_date,
            )
            for item in value.affiliations
        ),
    )


class StaffStoreAdapter(StaffStoreReference):
    """店舗Repositoryから配属用の固定値だけを返す。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def get(
        self, *, corporate_id: CorporateId, store_id: StoreId
    ) -> StoreSource | None:
        store = await self._repository.get(store_id)
        if store is None or store.corporate_id != corporate_id:
            return None
        return staff_store_source(store)


class ManagerStaffAdapter(ManagerStaffReference):
    """スタッフRepositoryから任命用の固定値だけを返す。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def get(
        self, *, corporate_id: CorporateId, staff_id: StaffId
    ) -> ManagerStaffSource | None:
        staff = await self._repository.get(corporate_id=corporate_id, staff_id=staff_id)
        if staff is None or staff.corporate_id != corporate_id:
            return None
        return manager_staff_source(staff)
