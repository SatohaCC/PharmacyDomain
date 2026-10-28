"""Repositoryから参照用DTOを投影するアダプタ。保存は行わない。"""

from __future__ import annotations

from app.application.medicine_catalog.errors import MedicineNotFoundError
from app.application.medicine_catalog.interfaces.get_effective_medicine_query_reader import (
    GetEffectiveMedicineQueryReader,
)
from app.application.medicine_catalog.queries.dtos.get_medicine import MedicineDto
from app.application.medicine_catalog.queries.models import GetEffectiveMedicineQuery
from app.application.medicine_catalog.values import parse_enum, required_text
from app.domain.medicine_catalog.primitives import MedicineCode, MedicineCodeType
from app.domain.medicine_catalog.repositories import MedicineCatalogRepository
from app.domain.medicine_catalog.value_objects import MedicineIdentifier


class GetEffectiveMedicineProjection(GetEffectiveMedicineQueryReader):
    """薬品コードと適用日からマスタ行を取得する。

    参照であってもベンダーシステム管理者専用にする。医薬品マスタは法人に
    属さないため対象法人を決められず、法人管理者の権限判定
    （``require_active(corporate_id=...)``）に載せられない。薬剤師向けの
    参照が必要になった時点で、非テナントの参照権限をどう表すかを決める。
    """

    def __init__(self, repository: MedicineCatalogRepository) -> None:
        self._repository = repository

    async def read(self, query: GetEffectiveMedicineQuery) -> MedicineDto:
        """指定日に有効なマスタ行をDTOで返す。"""
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
