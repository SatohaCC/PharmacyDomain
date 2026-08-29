"""医薬品マスタをApplication DTOへ変換して取得する処理。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import AuthorizationService, Permission
from app.application.medicine_catalog.exceptions import MedicineNotFoundError
from app.application.medicine_catalog.support import parse_enum, required_text
from app.base.domain.medicine import (
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
)
from app.domain.medicine_catalog import Medicine, MedicineCatalogRepository


@dataclass(frozen=True, kw_only=True)
class MedicineDto:
    """医薬品マスタ1行の出力DTO。

    導出値（``is_narcotic`` 等）も返す。呼び出し側が生の事実から判定し直すと、
    規則の実装が2箇所に分かれる。
    """

    id: str
    code_type: str
    code: str
    name: str
    unit: str
    dosage_form: str
    listed_on: str
    withdrawn_on: str | None
    catalog_version: str
    narcotic_category: str
    generic_category: str
    has_dosage_limit: bool
    is_analgesic_antiinflammatory: bool
    is_dermatological: bool
    is_narcotic: bool
    is_refill_restricted_patch: bool
    forbids_refill: bool

    @classmethod
    def from_entity(cls, medicine: Medicine) -> MedicineDto:
        """マスタ行からDTOを生成する。"""
        code = medicine.identifier.code
        withdrawn_on = medicine.effective_period.withdrawn_on
        return cls(
            id=str(medicine.id.value),
            code_type=medicine.identifier.code_type.value,
            code=code.value if code is not None else "",
            name=medicine.name.value,
            unit=medicine.unit.value,
            dosage_form=medicine.dosage_form.value,
            listed_on=medicine.effective_period.listed_on.value.isoformat(),
            withdrawn_on=(
                withdrawn_on.value.isoformat() if withdrawn_on is not None else None
            ),
            catalog_version=medicine.catalog_version.value.isoformat(),
            narcotic_category=medicine.narcotic_category.value,
            generic_category=medicine.generic_category.value,
            has_dosage_limit=medicine.has_dosage_limit,
            is_analgesic_antiinflammatory=medicine.is_analgesic_antiinflammatory,
            is_dermatological=medicine.is_dermatological,
            is_narcotic=medicine.is_narcotic,
            is_refill_restricted_patch=medicine.is_refill_restricted_patch,
            forbids_refill=medicine.forbids_refill,
        )


@dataclass(frozen=True, kw_only=True)
class GetEffectiveMedicineQuery:
    """指定日に有効なマスタ行の取得の入力データ。"""

    code_type: str
    code: str
    #: 適用日。麻薬指定も経過措置も時点で変わるので必須にする。
    as_of: date


class GetEffectiveMedicineUseCase:
    """薬品コードと適用日からマスタ行を取得する。

    参照であってもベンダーシステム管理者専用にする。医薬品マスタは法人に
    属さないため対象法人を決められず、法人管理者の権限判定
    （``require_active(corporate_id=...)``）に載せられない。薬剤師向けの
    参照が必要になった時点で、非テナントの参照権限をどう表すかを決める。
    """

    def __init__(
        self,
        repository: MedicineCatalogRepository,
        authorization: AuthorizationService,
    ) -> None:
        self._repository = repository
        self._authorization = authorization

    async def execute(self, query: GetEffectiveMedicineQuery) -> MedicineDto:
        """指定日に有効なマスタ行をDTOで返す。"""
        self._authorization.require_vendor_system_admin(
            permission=Permission.MANAGE_MEDICINE_CATALOG
        )
        identifier = MedicineIdentifier(
            code_type=parse_enum(MedicineCodeType, query.code_type, "薬品コード種別"),
            code=MedicineCode(required_text(query.code, "薬品コード")),
        )
        medicine = await self._repository.find_effective(
            identifier=identifier, as_of=query.as_of
        )
        if medicine is None:
            raise MedicineNotFoundError()
        return MedicineDto.from_entity(medicine)
