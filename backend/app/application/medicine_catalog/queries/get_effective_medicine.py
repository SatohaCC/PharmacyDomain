"""Applicationのget_effective_medicineを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.policies import AuthorizationService
from app.application.medicine_catalog.interfaces.get_effective_medicine_query_reader import (
    GetEffectiveMedicineQueryReader,
)
from app.application.medicine_catalog.queries.dtos.get_medicine import MedicineDto
from app.application.medicine_catalog.queries.models import GetEffectiveMedicineQuery
from app.application.medicine_catalog.values import parse_enum, required_text
from app.domain.medicine_catalog.primitives import MedicineCode, MedicineCodeType
from app.domain.medicine_catalog.value_objects import MedicineIdentifier


class GetEffectiveMedicineUseCase:
    def __init__(
        self,
        reader: GetEffectiveMedicineQueryReader,
        authorization: AuthorizationService,
    ) -> None:
        self._reader = reader
        self._authorization = authorization

    async def execute(self, query: GetEffectiveMedicineQuery) -> MedicineDto:
        """指定日に有効なマスタ行をDTOで返す。"""
        self._authorization.require_vendor_system_admin(
            permission=Permission.MANAGE_MEDICINE_CATALOG
        )
        MedicineIdentifier(
            code_type=parse_enum(MedicineCodeType, query.code_type, "薬品コード種別"),
            code=MedicineCode(required_text(query.code, "薬品コード")),
        )
        return await self._reader.read(query)
