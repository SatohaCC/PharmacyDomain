"""法人集約のエンティティ・ID・リポジトリインターフェース。"""

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.exceptions import (
    CorporateDomainError,
    CorporateNameAlreadyExistsError,
)
from app.domain.corporate.primitives import (
    CorporateId,
    CorporateName,
    CorporateRepresentativeName,
    CorporateStatus,
)
from app.domain.corporate.repository import (
    CorporateCatalogRepository,
    CorporateRepository,
)
from app.domain.corporate.services import CorporateNameUniquenessService

__all__ = [
    "Corporate",
    "CorporateCatalogRepository",
    "CorporateDomainError",
    "CorporateId",
    "CorporateName",
    "CorporateNameAlreadyExistsError",
    "CorporateNameUniquenessService",
    "CorporateRepository",
    "CorporateRepresentativeName",
    "CorporateStatus",
]
