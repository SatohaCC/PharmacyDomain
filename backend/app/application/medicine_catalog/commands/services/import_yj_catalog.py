"""Applicationのimport_yj_catalogを定義する。"""

from __future__ import annotations

import csv
import io
from datetime import date

from app.application.medicine_catalog.commands.models import (
    _DEFAULT_UNIT_BY_DOSAGE_FORM,
    _DOSAGE_FORM_BY_CHAR,
    DEFAULT_CATALOG_VERSION,
    DEFAULT_LISTED_ON,
)
from app.application.medicine_catalog.errors import YjCatalogParseError
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
from app.domain.medicine_catalog.value_objects import (
    MedicineEffectivePeriod,
    MedicineIdentifier,
)


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
                and (listed_on > withdrawn_on)
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
                    code_type=MedicineCodeType.YJ, code=MedicineCode(yj_code)
                ),
                name=MedicineName(med_name),
                unit=MedicineUnit(unit_str),
                effective_period=MedicineEffectivePeriod(
                    listed_on=MedicineListedOn(listed_on),
                    withdrawn_on=MedicineWithdrawnOn(withdrawn_on)
                    if withdrawn_on is not None
                    else None,
                ),
                catalog_version=MedicineCatalogVersion(version),
                dosage_form=dosage_form,
                narcotic_category=narcotic_category,
                generic_category=generic_category,
                is_analgesic_antiinflammatory=is_analgesic_antiinflammatory,
            )
            medicines.append(medicine)
        return medicines

    def _parse_date(
        self, raw: str, *, line_num: int, field_name: str, default: date | None
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
