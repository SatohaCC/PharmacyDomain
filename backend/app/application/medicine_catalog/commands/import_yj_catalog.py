"""Applicationのimport_yj_catalogを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.policies import AuthorizationService
from app.application.medicine_catalog.commands.dtos.import_yj_catalog import (
    ImportYjCatalogResultDto,
)
from app.application.medicine_catalog.commands.models import DEFAULT_CATALOG_VERSION
from app.application.medicine_catalog.commands.services.import_yj_catalog import (
    YjCatalogCsvParser,
)
from app.application.medicine_catalog.errors import YjCatalogParseError
from app.domain.medicine_catalog.repositories import MedicineCatalogRepository


@dataclass(frozen=True, kw_only=True)
class ImportYjCatalogCommand:
    """YJコードリストCSVインポートのコマンド。"""

    csv_text: str | None = None
    catalog_version: date | None = None


class ImportYjCatalogUseCase:
    """YJコードリストCSVを一括インポートするユースケース。"""

    def __init__(
        self,
        repository: MedicineCatalogRepository,
        authorization: AuthorizationService,
        parser: YjCatalogCsvParser | None = None,
        chunk_size: int = 1000,
    ) -> None:
        self._repository = repository
        self._authorization = authorization
        self._parser = parser or YjCatalogCsvParser()
        self._chunk_size = chunk_size

    async def execute(
        self, command: ImportYjCatalogCommand
    ) -> ImportYjCatalogResultDto:
        """CSVインポートを実行する。"""
        self._authorization.require_vendor_system_admin(
            permission=Permission.MANAGE_MEDICINE_CATALOG
        )
        if command.csv_text is not None:
            medicines = self._parser.parse_text(
                command.csv_text, catalog_version=command.catalog_version
            )
        else:
            raise YjCatalogParseError("CSV文字列が指定されていません。")
        version = command.catalog_version or (
            medicines[0].catalog_version.value if medicines else DEFAULT_CATALOG_VERSION
        )
        for i in range(0, len(medicines), self._chunk_size):
            chunk = medicines[i : i + self._chunk_size]
            await self._repository.save_all(chunk)
        return ImportYjCatalogResultDto(
            total_rows=len(medicines),
            imported_count=len(medicines),
            skipped_count=0,
            catalog_version=version,
        )
