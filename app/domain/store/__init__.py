"""店舗集約のエンティティ・値オブジェクト・リポジトリインターフェース。"""

from app.domain.store.exceptions import (
    InsurancePharmacyNumberAlreadyExistsError,
    StoreCodeAlreadyExistsError,
    StoreDomainError,
    StoreNameAlreadyExistsError,
)
from app.domain.store.primitives import (
    ContactInfo,
    InsurancePharmacyNumber,
    StoreAddress,
    StoreAddressLine,
    StoreCode,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreId,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StoreNames,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.repository import StoreCatalogRepository, StoreRepository
from app.domain.store.services import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.domain.store.store import Store

__all__ = [
    "ContactInfo",
    "InsurancePharmacyNumber",
    "InsurancePharmacyNumberAlreadyExistsError",
    "InsurancePharmacyNumberUniquenessService",
    "Store",
    "StoreAddress",
    "StoreAddressLine",
    "StoreCatalogRepository",
    "StoreCode",
    "StoreCodeAlreadyExistsError",
    "StoreCodeUniquenessService",
    "StoreDomainError",
    "StoreEmailAddress",
    "StoreFaxNumber",
    "StoreId",
    "StoreName",
    "StoreNameAlreadyExistsError",
    "StoreNameKana",
    "StoreNameRomaji",
    "StoreNameUniquenessService",
    "StoreNames",
    "StorePhoneNumber",
    "StorePostalCode",
    "StoreRepository",
]
