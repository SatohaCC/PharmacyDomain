"""Applicationのupdate_certificationsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.store.commands.services.support import load_store_or_raise
from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import (
    DiseaseCategory,
    PublicExpenseDesignationNumber,
)
from app.domain.store.repositories import StoreRepository
from app.domain.store.value_objects import (
    CommunityLinkageCertification,
    HealthSupportPharmacyNotification,
    PharmacyCertifications,
    SpecializedLinkageCertification,
)


@dataclass(frozen=True, kw_only=True)
class CommunityLinkageInput:
    """地域連携薬局認定の入力データ。"""

    certification_number: str
    valid_from: date
    valid_to: date


@dataclass(frozen=True, kw_only=True)
class SpecializedLinkageInput:
    """専門医療機関連携薬局認定の入力データ。"""

    certification_number: str
    disease_category: str
    valid_from: date
    valid_to: date


@dataclass(frozen=True, kw_only=True)
class HealthSupportNotificationInput:
    """健康サポート薬局届出の入力データ。"""

    notified_on: date


@dataclass(frozen=True, kw_only=True)
class UpdateCertificationsCommand:
    """薬局機能認定・届出更新コマンド。"""

    corporate_id: str
    store_id: str
    community_linkage: CommunityLinkageInput | None = None
    specialized_linkage: SpecializedLinkageInput | None = None
    health_support: HealthSupportNotificationInput | None = None


class UpdateCertificationsUseCase:
    """店舗の薬局機能認定・届出更新ユースケース。"""

    def __init__(
        self, repository: StoreRepository, corporate_access: CorporateAccessBoundary
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(self, command: UpdateCertificationsCommand) -> None:
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_STORE
        )
        store_id = StoreId.parse(command.store_id)
        store = await load_store_or_raise(
            self._repository, corporate_id=corporate_id, store_id=store_id
        )

        community_linkage = None
        if command.community_linkage is not None:
            community_linkage = CommunityLinkageCertification(
                certification_number=PublicExpenseDesignationNumber(
                    command.community_linkage.certification_number
                ),
                valid_from=command.community_linkage.valid_from,
                valid_to=command.community_linkage.valid_to,
            )

        specialized_linkage = None
        if command.specialized_linkage is not None:
            try:
                cat = DiseaseCategory(command.specialized_linkage.disease_category)
            except ValueError as err:
                raise DomainValidationError(
                    f"不正な傷病区分です: '{command.specialized_linkage.disease_category}'"
                ) from err
            specialized_linkage = SpecializedLinkageCertification(
                certification_number=PublicExpenseDesignationNumber(
                    command.specialized_linkage.certification_number
                ),
                disease_category=cat,
                valid_from=command.specialized_linkage.valid_from,
                valid_to=command.specialized_linkage.valid_to,
            )

        health_support = None
        if command.health_support is not None:
            health_support = HealthSupportPharmacyNotification(
                notified_on=command.health_support.notified_on,
            )

        certifications = PharmacyCertifications(
            community_linkage=community_linkage,
            specialized_linkage=specialized_linkage,
            health_support=health_support,
        )
        updated = store.update_certifications(certifications)
        await self._repository.save(updated)
