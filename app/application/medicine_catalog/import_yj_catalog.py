"""YJコードリストCSVのインポートユースケースおよびパーサー。"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.application.access_control import AuthorizationService, Permission
from app.application.common.exceptions import ApplicationError
from app.domain.medicine_catalog.medicine import Medicine, MedicineEffectivePeriod
from app.domain.medicine_catalog.primitives import (
    GenericCategory,
    MedicineCatalogVersion,
    MedicineDosageForm,
    MedicineListedOn,
    MedicineWithdrawnOn,
    NarcoticCategory,
)
from app.domain.medicine_catalog.repository import MedicineCatalogRepository
from app.domain.shared.medicine import (
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineName,
    MedicineUnit,
)

DEFAULT_CATALOG_VERSION = date(2026, 8, 15)
DEFAULT_LISTED_ON = date(1950, 1, 1)

_DOSAGE_FORM_BY_CHAR: dict[str, MedicineDosageForm] = {
    "F": MedicineDosageForm.TABLET,
    "K": MedicineDosageForm.TABLET,
    "M": MedicineDosageForm.CAPSULE,
    "B": MedicineDosageForm.POWDER,
    "C": MedicineDosageForm.POWDER,
    "R": MedicineDosageForm.POWDER,
    "G": MedicineDosageForm.LIQUID,
    "U": MedicineDosageForm.LIQUID,
    "A": MedicineDosageForm.INJECTION,
    "D": MedicineDosageForm.INJECTION,
    "E": MedicineDosageForm.INJECTION,
    "L": MedicineDosageForm.INJECTION,
    "S": MedicineDosageForm.PATCH,
    "P": MedicineDosageForm.PATCH,
    "Q": MedicineDosageForm.OINTMENT,
    "V": MedicineDosageForm.OINTMENT,
    "N": MedicineDosageForm.EYE_DROP,
    "J": MedicineDosageForm.SUPPOSITORY,
    "X": MedicineDosageForm.OTHER,
    "Y": MedicineDosageForm.OTHER,
    "H": MedicineDosageForm.OTHER,
    "T": MedicineDosageForm.OTHER,
    "W": MedicineDosageForm.OTHER,
}

_DEFAULT_UNIT_BY_DOSAGE_FORM: dict[MedicineDosageForm, str] = {
    MedicineDosageForm.TABLET: "錠",
    MedicineDosageForm.CAPSULE: "カプセル",
    MedicineDosageForm.POWDER: "ｇ",
    MedicineDosageForm.LIQUID: "ｍＬ",
    MedicineDosageForm.INJECTION: "管",
    MedicineDosageForm.PATCH: "枚",
    MedicineDosageForm.OINTMENT: "ｇ",
    MedicineDosageForm.EYE_DROP: "ｍＬ",
    MedicineDosageForm.SUPPOSITORY: "個",
    MedicineDosageForm.OTHER: "個",
}


class YjCatalogParseError(ApplicationError):
    """YJコードリストCSVの構文解析エラー。"""

    default_message = "YJコードリストCSVの解析に失敗しました。"
    default_code = "YJ_CATALOG_PARSE_ERROR"


@dataclass(frozen=True, kw_only=True)
class ImportYjCatalogCommand:
    """YJコードリストCSVインポートのコマンド。"""

    csv_text: str | None = None
    file_path: str | None = None
    catalog_version: date | None = None


@dataclass(frozen=True, kw_only=True)
class ImportYjCatalogResultDto:
    """インポート実行結果DTO。"""

    total_rows: int
    imported_count: int
    skipped_count: int
    catalog_version: date


class YjCatalogCsvParser:
    """YJコードリストCSVをパースしてMedicine集約を構築するパーサー。"""

    def parse_text(
        self, text: str, *, catalog_version: date | None = None
    ) -> list[Medicine]:
        """CSV文字列からMedicine集約のリストをパースする。"""
        version = catalog_version or DEFAULT_CATALOG_VERSION
        medicines: list[Medicine] = []
        reader = csv.reader(io.StringIO(text))
        header_skipped = False

        for line_num, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue

            first_cell = row[0].strip()
            if not header_skipped and (
                "ＹＪコード" in first_cell
                or "YJコード" in first_cell
                or "医薬品名" in "".join(row)
            ):
                header_skipped = True
                continue

            if len(row) < 2:
                raise YjCatalogParseError(
                    f"{line_num}行目: CSV列数が不足しています（医薬品名までの2列以上が必要です）。"
                )

            yj_code = first_cell
            if len(yj_code) != 12 or not yj_code.isalnum():
                raise YjCatalogParseError(
                    f"{line_num}行目: YJコードが不正です（12桁英数字が必要です）: {yj_code}"
                )

            med_name = row[1].strip()
            if not med_name:
                raise YjCatalogParseError(f"{line_num}行目: 医薬品名が空です。")

            company_name = row[2].strip() if len(row) > 2 else ""

            listed_on = self._parse_date(
                row[3].strip() if len(row) > 3 else "",
                line_num=line_num,
                field_name="リスト登録年月日",
                default=DEFAULT_LISTED_ON,
            )
            withdrawn_on = self._parse_date(
                row[4].strip() if len(row) > 4 else "",
                line_num=line_num,
                field_name="リスト除外年月日",
                default=None,
            )
            if (
                listed_on is not None
                and withdrawn_on is not None
                and listed_on > withdrawn_on
            ):
                raise YjCatalogParseError(
                    f"{line_num}行目: 登録年月日({listed_on})が除外年月日({withdrawn_on})より未来です。"
                )

            dosage_char = yj_code[7].upper()
            dosage_form = _DOSAGE_FORM_BY_CHAR.get(
                dosage_char, MedicineDosageForm.OTHER
            )

            unit_str = self._extract_unit(med_name, dosage_form)

            if yj_code.startswith("811"):
                narcotic_category = NarcoticCategory.NARCOTIC
            elif yj_code.startswith("821"):
                narcotic_category = NarcoticCategory.STIMULANT_RAW_MATERIAL
            else:
                narcotic_category = NarcoticCategory.NONE

            if "「" in med_name and "」" in med_name:
                generic_category = GenericCategory.GENERIC
            elif company_name:
                generic_category = GenericCategory.BRAND
            else:
                generic_category = GenericCategory.OTHER

            is_analgesic_antiinflammatory = (
                dosage_form == MedicineDosageForm.PATCH
                and (yj_code.startswith("114") or yj_code.startswith("264"))
            )

            assert listed_on is not None
            medicine = Medicine.register(
                identifier=MedicineIdentifier(
                    code_type=MedicineCodeType.YJ,
                    code=MedicineCode(yj_code),
                ),
                name=MedicineName(med_name),
                unit=MedicineUnit(unit_str),
                effective_period=MedicineEffectivePeriod(
                    listed_on=MedicineListedOn(listed_on),
                    withdrawn_on=(
                        MedicineWithdrawnOn(withdrawn_on)
                        if withdrawn_on is not None
                        else None
                    ),
                ),
                catalog_version=MedicineCatalogVersion(version),
                dosage_form=dosage_form,
                narcotic_category=narcotic_category,
                generic_category=generic_category,
                is_analgesic_antiinflammatory=is_analgesic_antiinflammatory,
            )
            medicines.append(medicine)

        return medicines

    def parse_file(
        self, path: Path | str, *, catalog_version: date | None = None
    ) -> list[Medicine]:
        """CSVファイルからMedicine集約のリストをパースする。"""
        file_path = Path(path)
        if not file_path.exists():
            raise YjCatalogParseError(f"指定されたファイルが存在しません: {file_path}")
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = file_path.read_text(encoding="cp932")
        return self.parse_text(text, catalog_version=catalog_version)

    def _parse_date(
        self,
        raw: str,
        *,
        line_num: int,
        field_name: str,
        default: date | None,
    ) -> date | None:
        if not raw:
            return default
        if len(raw) != 8 or not raw.isdigit():
            raise YjCatalogParseError(
                f"{line_num}行目: {field_name}の日付形式が不正です（YYYYMMDD 8桁が必要です）: {raw}"
            )
        try:
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        except ValueError as exc:
            raise YjCatalogParseError(
                f"{line_num}行目: {field_name}の日付が無効です: {raw}"
            ) from exc

    def _extract_unit(self, name: str, dosage_form: MedicineDosageForm) -> str:
        if "カプセル" in name or "Cap" in name:
            return "カプセル"
        if "錠" in name:
            return "錠"
        if any(
            k in name for k in ("テープ", "パップ", "プラスター", "貼付", "貼", "枚")
        ):
            return "枚"
        if "注" in name or "管" in name:
            return "管"
        if "包" in name:
            return "包"
        if "キット" in name:
            return "キット"
        if "本" in name:
            return "本"
        if "瓶" in name:
            return "瓶"
        if "坐剤" in name or "坐薬" in name:
            return "個"
        if any(k in name for k in ("軟膏", "クリーム", "ゲル")):
            return "ｇ"
        if any(
            k in name for k in ("散", "顆粒", "細粒", "ドライシロップ", "ＤＳ", "末")
        ):
            return "ｇ"
        if any(
            k in name for k in ("点眼", "点鼻", "液", "シロップ", "内用液", "外用液")
        ):
            return "ｍＬ"
        return _DEFAULT_UNIT_BY_DOSAGE_FORM.get(dosage_form, "個")


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
        elif command.file_path is not None:
            medicines = self._parser.parse_file(
                command.file_path, catalog_version=command.catalog_version
            )
        else:
            raise YjCatalogParseError(
                "CSV文字列またはファイルパスが指定されていません。"
            )

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
