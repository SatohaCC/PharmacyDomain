"""Applicationのregister_medicineを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.policies import AuthorizationService
from app.application.medicine_catalog.commands.dtos.get_medicine import MedicineDto
from app.application.medicine_catalog.values import parse_enum, required_text
from app.domain.medicine_catalog.entities import Medicine
from app.domain.medicine_catalog.primitives import (
    GenericCategory,
    MedicineCatalogVersion,
    MedicineCode,
    MedicineCodeType,
    MedicineDosageForm,
    MedicineListedOn,
    MedicineName,
    MedicineUnit,
    MedicineWithdrawnOn,
    NarcoticCategory,
)
from app.domain.medicine_catalog.repositories import MedicineCatalogRepository
from app.domain.medicine_catalog.services import MedicineEffectivePeriodConflictService
from app.domain.medicine_catalog.value_objects import (
    MedicineEffectivePeriod,
    MedicineIdentifier,
)


@dataclass(frozen=True, kw_only=True)
class RegisterMedicineCommand:
    """医薬品マスタ取り込みの入力データ。"""

    code_type: str
    code: str
    name: str
    unit: str
    dosage_form: str
    listed_on: date
    catalog_version: date
    withdrawn_on: date | None = None
    narcotic_category: str = NarcoticCategory.NONE.value
    generic_category: str = GenericCategory.OTHER.value
    has_dosage_limit: bool = False
    is_analgesic_antiinflammatory: bool = False
    is_dermatological: bool = False


class RegisterMedicineUseCase:
    """薬価基準収載品目を1件取り込む。"""

    def __init__(
        self,
        repository: MedicineCatalogRepository,
        authorization: AuthorizationService,
        conflict_service: MedicineEffectivePeriodConflictService,
    ) -> None:
        self._repository = repository
        self._authorization = authorization
        self._conflict_service = conflict_service

    async def execute(self, command: RegisterMedicineCommand) -> MedicineDto:
        """収載期間の重複を確認してマスタ行を保存する。"""
        self._authorization.require_vendor_system_admin(
            permission=Permission.MANAGE_MEDICINE_CATALOG
        )
        identifier = MedicineIdentifier(
            code_type=parse_enum(MedicineCodeType, command.code_type, "薬品コード種別"),
            code=MedicineCode(required_text(command.code, "薬品コード")),
        )
        medicine = Medicine.register(
            identifier=identifier,
            name=MedicineName(required_text(command.name, "薬品名称")),
            unit=MedicineUnit(required_text(command.unit, "単位名")),
            effective_period=MedicineEffectivePeriod(
                listed_on=MedicineListedOn(command.listed_on),
                withdrawn_on=MedicineWithdrawnOn(command.withdrawn_on)
                if command.withdrawn_on is not None
                else None,
            ),
            catalog_version=MedicineCatalogVersion(command.catalog_version),
            dosage_form=parse_enum(MedicineDosageForm, command.dosage_form, "剤形"),
            narcotic_category=parse_enum(
                NarcoticCategory, command.narcotic_category, "麻薬・向精神薬区分"
            ),
            generic_category=parse_enum(
                GenericCategory, command.generic_category, "先発・後発の別"
            ),
            has_dosage_limit=command.has_dosage_limit,
            is_analgesic_antiinflammatory=command.is_analgesic_antiinflammatory,
            is_dermatological=command.is_dermatological,
        )
        existing = await self._repository.list_versions(identifier)
        self._conflict_service.ensure_no_conflict(medicine, existing)
        await self._repository.save(medicine)
        return MedicineDto.from_entity(medicine)
