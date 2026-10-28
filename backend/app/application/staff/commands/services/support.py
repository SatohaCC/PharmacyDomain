"""Applicationのsupportを定義する。"""

from __future__ import annotations

from app.application.staff.errors import StaffNotFoundError
from app.application.staff.interfaces.references import StaffStoreReference
from app.application.store.errors import StoreNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.value_objects import StoreSource
from app.domain.store.identifiers import StoreId


async def load_staff_or_raise(
    repository: StaffRepository, *, corporate_id: CorporateId, staff_id: StaffId
) -> Staff:
    """指定された法人に所属するスタッフを取得し、存在しないまたは別法人の場合は例外を送出する。"""
    staff = await repository.get(corporate_id=corporate_id, staff_id=staff_id)
    if staff is None:
        raise StaffNotFoundError(
            f"指定されたスタッフ（ID: {staff_id.value}）が見つかりません。"
        )
    return staff


async def load_store_or_raise(
    repository: StaffStoreReference, *, corporate_id: CorporateId, store_id: StoreId
) -> StoreSource:
    """別法人の存在を隠し、配属用の店舗事実だけを読み込む。"""
    store = await repository.get(corporate_id=corporate_id, store_id=store_id)
    if store is None:
        raise StoreNotFoundError(
            f"指定された店舗（ID: {store_id.value}）が見つかりません。"
        )
    return store
