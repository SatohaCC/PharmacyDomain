"""NSIPS CSV/TSV 構文解析エンジン。"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from app.application.integration.nsips.exceptions import NsipsParseError
from app.application.integration.nsips.models import (
    NsipsBundle,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
    NsipsSplitInfo,
)


class NsipsParser:
    """NSIPS形式のテキストを解析して NsipsBundle を構築するパーサー。"""

    def parse(self, raw_text: str) -> NsipsBundle:
        """NSIPSテキストをパースする。"""
        if not raw_text or not raw_text.strip():
            raise NsipsParseError("NSIPSテキストが空です。")

        reader = csv.reader(io.StringIO(raw_text.strip()))

        raw_prescription: dict[str, str] | None = None
        raw_patient: dict[str, str] | None = None
        raw_split: NsipsSplitInfo | None = None
        rp_dict: dict[int, dict[str, object]] = {}

        for line_idx, row in enumerate(reader, start=1):
            if not row:
                continue
            cols = [col.strip() for col in row]
            if not cols or not cols[0]:
                continue

            record_type = cols[0]

            if record_type in ("1", "01"):
                raw_prescription = self._parse_prescription_record(cols, line_idx)
            elif record_type in ("2", "02"):
                raw_patient = self._parse_patient_record(cols, line_idx)
            elif record_type in ("5", "05", "4", "04"):
                self._parse_rp_record(cols, line_idx, rp_dict)
            elif record_type in ("6", "06"):
                raw_split = self._parse_split_record(cols, line_idx)

        if raw_prescription is None:
            raise NsipsParseError("処方基本レコード(1)が存在しません。")
        if raw_patient is None:
            raise NsipsParseError("患者レコード(2)が存在しません。")

        # 患者情報の構築
        patient = NsipsPatientInfo(
            external_patient_id=raw_patient["external_patient_id"],
            kanji_name=raw_patient["kanji_name"],
            kana_name=raw_patient["kana_name"],
            birth_date=self._parse_date(raw_patient["birth_date"], "患者生年月日"),
            gender=raw_patient["gender"],
            postal_code=raw_patient.get("postal_code") or None,
            address=raw_patient.get("address") or None,
            phone_number=raw_patient.get("phone_number") or None,
        )

        # Rp情報の構築
        rps: list[NsipsRpInfo] = []
        for rp_num in sorted(rp_dict.keys()):
            rp_data = rp_dict[rp_num]
            raw_meds = rp_data["medicines"]
            meds: list[NsipsMedicineInfo] = (
                raw_meds if isinstance(raw_meds, list) else []
            )
            raw_prep = rp_data.get("preparation_method")
            preparation_method = str(raw_prep) if raw_prep is not None else None
            rps.append(
                NsipsRpInfo(
                    rp_number=rp_num,
                    group_name=str(rp_data["group_name"]),
                    instructions=str(rp_data["instructions"]),
                    dispensing_quantity=int(str(rp_data["dispensing_quantity"])),
                    medicines=tuple(meds),
                    preparation_method=preparation_method,
                )
            )

        prescription = NsipsPrescriptionInfo(
            document_number=raw_prescription["document_number"],
            issued_date=self._parse_date(
                raw_prescription["issued_date"], "処方箋交付日"
            ),
            institution_code=raw_prescription["institution_code"],
            institution_name=raw_prescription["institution_name"],
            department_code=raw_prescription.get("department_code") or None,
            department_name=raw_prescription.get("department_name") or None,
            doctor_name=raw_prescription["doctor_name"],
            rps=tuple(rps),
            split_info=raw_split,
        )

        return NsipsBundle(
            header_version="1.0",
            patient=patient,
            prescription=prescription,
        )

    def _parse_prescription_record(
        self, cols: list[str], line_idx: int
    ) -> dict[str, str]:
        if len(cols) < 5:
            raise NsipsParseError(
                f"{line_idx}行目: 処方基本レコードの列数が不足しています。"
            )
        issued_date = cols[1] if len(cols) > 1 else ""
        doc_num = cols[2] if len(cols) > 2 else ""
        inst_code = cols[3] if len(cols) > 3 else ""
        inst_name = cols[4] if len(cols) > 4 else ""

        if not doc_num:
            raise NsipsParseError(f"{line_idx}行目: 処方箋番号が指定されていません。")
        if not inst_code or not inst_name:
            raise NsipsParseError(f"{line_idx}行目: 医療機関情報が不足しています。")

        dept_code = cols[5] if len(cols) > 5 else ""
        dept_name = cols[6] if len(cols) > 6 else ""
        doctor_name = cols[7] if len(cols) > 7 else ""

        return {
            "issued_date": issued_date,
            "document_number": doc_num,
            "institution_code": inst_code,
            "institution_name": inst_name,
            "department_code": dept_code,
            "department_name": dept_name,
            "doctor_name": doctor_name,
        }

    def _parse_patient_record(self, cols: list[str], line_idx: int) -> dict[str, str]:
        if len(cols) < 5:
            raise NsipsParseError(
                f"{line_idx}行目: 患者レコードの列数が不足しています。"
            )
        pat_id = cols[1] if len(cols) > 1 else ""
        kana_name = cols[2] if len(cols) > 2 else ""
        kanji_name = cols[3] if len(cols) > 3 else ""
        gender = cols[4] if len(cols) > 4 else "0"
        birth_date = cols[5] if len(cols) > 5 else ""

        if not pat_id:
            raise NsipsParseError(f"{line_idx}行目: 患者番号が指定されていません。")
        if not kanji_name and not kana_name:
            raise NsipsParseError(f"{line_idx}行目: 患者氏名が指定されていません。")

        postal_code = cols[6] if len(cols) > 6 else ""
        address = cols[7] if len(cols) > 7 else ""
        phone = cols[8] if len(cols) > 8 else ""

        return {
            "external_patient_id": pat_id,
            "kana_name": kana_name or kanji_name,
            "kanji_name": kanji_name or kana_name,
            "gender": gender,
            "birth_date": birth_date,
            "postal_code": postal_code,
            "address": address,
            "phone_number": phone,
        }

    def _parse_rp_record(
        self,
        cols: list[str],
        line_idx: int,
        rp_dict: dict[int, dict[str, object]],
    ) -> None:
        if len(cols) < 9:
            raise NsipsParseError(
                f"{line_idx}行目: 処方明細レコードの列数が不足しています。"
            )
        try:
            rp_number = int(cols[1])
        except ValueError:
            raise NsipsParseError(
                f"{line_idx}行目: Rp番号が数値ではありません。"
            ) from None

        group_name = cols[2] if len(cols) > 2 else "内服"
        instructions = cols[3] if len(cols) > 3 else "用法指示なし"
        try:
            dispensing_qty = int(cols[4]) if len(cols) > 4 else 1
        except ValueError:
            dispensing_qty = 1

        med_code = cols[6] if len(cols) > 6 else ""
        med_name = cols[7] if len(cols) > 7 else ""
        try:
            dosage = Decimal(cols[8]) if len(cols) > 8 else Decimal("1")
        except InvalidOperation, ValueError:
            dosage = Decimal("1")

        unit = cols[9] if len(cols) > 9 else "錠"
        prep_flag = cols[10] if len(cols) > 10 else "0"

        prep_method: str | None = None
        if prep_flag == "1":
            prep_method = "PACKAGE_UNIT"
        elif prep_flag == "2":
            prep_method = "POWDERED"

        medicine = NsipsMedicineInfo(
            medicine_code=med_code,
            medicine_name=med_name,
            dosage=dosage,
            unit=unit,
        )

        if rp_number not in rp_dict:
            rp_dict[rp_number] = {
                "group_name": group_name,
                "instructions": instructions,
                "dispensing_quantity": dispensing_qty,
                "medicines": [medicine],
                "preparation_method": prep_method,
            }
        else:
            current_meds: list[NsipsMedicineInfo] = rp_dict[rp_number]["medicines"]  # type: ignore[assignment]
            current_meds.append(medicine)
            if prep_method:
                rp_dict[rp_number]["preparation_method"] = prep_method

    def _parse_split_record(self, cols: list[str], line_idx: int) -> NsipsSplitInfo:
        if len(cols) < 4:
            raise NsipsParseError(
                f"{line_idx}行目: 分割調剤レコードの列数が不足しています。"
            )
        try:
            iteration = int(cols[1])
            total_split = int(cols[2])
        except ValueError:
            raise NsipsParseError(
                f"{line_idx}行目: 分割回数が数値ではありません。"
            ) from None

        reason = cols[3]
        return NsipsSplitInfo(
            iteration=iteration,
            total_split_count=total_split,
            split_reason=reason,
        )

    def _parse_date(self, date_str: str, field_name: str) -> date:
        if not date_str or len(date_str) != 8:
            raise NsipsParseError(
                f"{field_name}の日付形式が不正です(YYYYMMDD形式が必要です): {date_str}"
            )
        try:
            year = int(date_str[0:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            return date(year, month, day)
        except ValueError as exc:
            raise NsipsParseError(f"{field_name}の日付が無効です: {date_str}") from exc
