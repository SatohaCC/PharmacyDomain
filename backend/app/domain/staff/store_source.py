"""スタッフ配属の判断に必要な店舗の固定値。"""

from dataclasses import dataclass

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.value_object import ValueObject
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class StoreSource(ValueObject):
    """店舗の同一性、法人、閉局事実だけを保持する。"""

    store_id: StoreId
    corporate_id: CorporateId
    is_closed: bool
