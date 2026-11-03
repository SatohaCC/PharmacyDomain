"""法人権限とは独立した店舗別の権限。"""

from dataclasses import dataclass

from app.domain.foundation.value_object import ValueObject
from app.domain.identity.primitives import StoreRole
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class StoreRoleAssignment(ValueObject):
    """一店舗に対する操作ロール。"""

    store_id: StoreId
    role: StoreRole
