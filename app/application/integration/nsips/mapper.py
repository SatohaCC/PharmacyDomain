"""NSIPS解析モデルから各ドメイン入力コマンドへのデータマッパー。"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.dispensing.inputs import (
    DispensedMedicineInput,
    DispensedRpInput,
)
from app.application.dispensing.start_dispensing import StartDispensingCommand
from app.application.integration.nsips.models import NsipsBundle
from app.application.medication_history.inputs import (
    AddFollowUpCommand,
    HandbookStatusInput,
    LabeledNoteInput,
    ResidualDrugInput,
    SoapInput,
)
from app.application.medication_history.start_medication_history import (
    StartMedicationHistoryCommand,
)
from app.application.patient.register_patient import RegisterPatientCommand
from app.application.prescription.inputs import (
    DepartmentInput,
    DosageInstructionInput,
    MedicalInstitutionInput,
    MedicineInput,
    PrescriberInput,
    RpInput,
)
from app.application.prescription.register_prescription import (
    RegisterPrescriptionCommand,
)


class NsipsDataMapper:
    """NsipsBundle からドメイン層の Command を生成する。"""

    @staticmethod
    def to_patient_command(
        bundle: NsipsBundle, corporate_id: str
    ) -> RegisterPatientCommand:
        """患者登録コマンドへ変換する。"""
        kanji = bundle.patient.kanji_name.strip()
        kana = bundle.patient.kana_name.strip()

        last_name, first_name = NsipsDataMapper._split_name(kanji)
        last_kana, first_kana = NsipsDataMapper._split_name(kana)

        return RegisterPatientCommand(
            corporate_id=corporate_id,
            last_name=last_name,
            first_name=first_name,
            last_name_kana=last_kana,
            first_name_kana=first_kana,
            birth_date=bundle.patient.birth_date,
        )

    @staticmethod
    def to_prescription_command(
        bundle: NsipsBundle,
        *,
        corporate_id: str,
        store_id: str,
        patient_id: str,
    ) -> RegisterPrescriptionCommand:
        """処方箋登録コマンドへ変換する。"""
        p = bundle.prescription

        # 医療機関
        pref_code = p.institution_code[:2] if len(p.institution_code) >= 2 else "13"
        institution = MedicalInstitutionInput(
            code_type="medical",
            code=p.institution_code,
            prefecture_code=pref_code,
            name=p.institution_name,
        )

        # 診療科
        dept_code = p.department_code or "01"
        dept_name = p.department_name or "内科"
        department = DepartmentInput(
            code_type="standard",
            code=dept_code,
            name=dept_name,
        )

        # 処方医
        doc_raw = p.doctor_name.strip()
        last_name, first_name = NsipsDataMapper._split_doctor_name(doc_raw)

        prescriber = PrescriberInput(
            last_name=last_name,
            first_name=first_name,
            last_name_kana="サトウ",
            first_name_kana="イシ",
        )

        # Rp
        rps: list[RpInput] = []
        for rp in p.rps:
            category = "internal"
            if rp.group_name == "外用":
                category = "topical"
            elif rp.group_name == "頓服":
                category = "prn"

            meds: list[MedicineInput] = []
            for idx, med in enumerate(rp.medicines, start=1):
                meds.append(
                    MedicineInput(
                        line_number=idx,
                        code_type="receipt",
                        code=med.medicine_code or None,
                        name=med.medicine_name,
                        amount=str(med.dosage),
                        unit=med.unit,
                    )
                )

            rps.append(
                RpInput(
                    rp_number=rp.rp_number,
                    category=category,
                    quantity=rp.dispensing_quantity,
                    dosage_instruction=DosageInstructionInput(
                        code_type="none",
                        name=rp.instructions,
                    ),
                    medicines=tuple(meds),
                )
            )

        return RegisterPrescriptionCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=patient_id,
            source_type="paper_qr",
            document_number=p.document_number,
            issued_date=p.issued_date,
            medical_institution=institution,
            department=department,
            prescriber=prescriber,
            rps=tuple(rps),
        )

    @staticmethod
    def to_dispensing_command(
        bundle: NsipsBundle,
        *,
        corporate_id: str,
        store_id: str,
        prescription_id: str,
        dispenser_id: str,
    ) -> StartDispensingCommand:
        """調剤開始コマンドへ変換する。"""
        p = bundle.prescription

        iteration = 1
        total_split = None
        split_reason = None
        if p.split_info:
            iteration = p.split_info.iteration
            total_split = p.split_info.total_split_count
            raw_reason = p.split_info.split_reason
            if raw_reason:
                if (
                    "長期" in raw_reason
                    or "保存" in raw_reason
                    or "storage" in raw_reason.lower()
                ):
                    split_reason = "long_term_storage"
                elif (
                    "後発" in raw_reason
                    or "試用" in raw_reason
                    or "trial" in raw_reason.lower()
                    or "generic" in raw_reason.lower()
                ):
                    split_reason = "generic_trial"
                elif (
                    "医師" in raw_reason
                    or "指示" in raw_reason
                    or "instruct" in raw_reason.lower()
                ):
                    split_reason = "prescriber_instructed"
                else:
                    split_reason = raw_reason

        dispensed_rps: list[DispensedRpInput] = []
        for rp in p.rps:
            category = "internal"
            if rp.group_name == "外用":
                category = "topical"
            elif rp.group_name == "頓服":
                category = "prn"

            meds: list[DispensedMedicineInput] = []
            for idx, med in enumerate(rp.medicines, start=1):
                preps: tuple[str, ...] = ()
                if rp.preparation_method:
                    pm_upper = rp.preparation_method.upper()
                    if (
                        "PACKAGE" in pm_upper
                        or "UNIT" in pm_upper
                        or "DOSE" in pm_upper
                    ):
                        preps = ("unit_dose_packaged",)
                    elif "POWDER" in pm_upper or "COMPOUND" in pm_upper:
                        preps = ("compounded",)
                    elif "MIX" in pm_upper:
                        preps = ("measured_mixing",)
                    else:
                        preps = (rp.preparation_method.lower(),)

                meds.append(
                    DispensedMedicineInput(
                        line_number=idx,
                        code_type="receipt",
                        code=med.medicine_code or None,
                        name=med.medicine_name,
                        amount=str(med.dosage),
                        unit=med.unit,
                        preparations=preps,
                    )
                )

            dispensed_rps.append(
                DispensedRpInput(
                    rp_number=rp.rp_number,
                    category=category,
                    quantity=rp.dispensing_quantity,
                    dosage_code_type="none",
                    dosage_name=rp.instructions,
                    medicines=tuple(meds),
                )
            )

        return StartDispensingCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            prescription_id=prescription_id,
            dispenser_id=dispenser_id,
            iteration=iteration,
            dispensed_date=p.issued_date,
            dispensed_rps=tuple(dispensed_rps),
            total_split_count=total_split,
            split_reason=split_reason,
        )

    @staticmethod
    def to_medication_history_command(
        bundle: NsipsBundle,
        *,
        corporate_id: str,
        store_id: str,
        dispensing_id: str,
        counselor_id: str,
    ) -> StartMedicationHistoryCommand:
        """薬歴下書き起票コマンドへ変換する。"""
        p = bundle.prescription

        med_lines: list[str] = []
        for rp in p.rps:
            med_names = ", ".join(m.medicine_name for m in rp.medicines)
            med_lines.append(f"Rp{rp.rp_number}: {med_names} ({rp.instructions})")

        obj_summary = "処方・調剤内容:\n" + "\n".join(med_lines)

        return StartMedicationHistoryCommand(
            corporate_id=corporate_id,
            store_id=store_id,
            dispensing_id=dispensing_id,
            counselor_id=counselor_id,
            method="face_to_face",
            soap=SoapInput(
                objective=(LabeledNoteInput(text=obj_summary),),
            ),
            handbook_status=HandbookStatusInput(
                presented=True,
            ),
            residual_drug=ResidualDrugInput(
                has_residual_drugs=False,
            ),
            information_sheet_provided=False,
            profile_updates=None,
        )

    @staticmethod
    def to_follow_up_command(
        bundle: NsipsBundle,
        *,
        corporate_id: str,
        record_id: str,
        counselor_id: str,
        followed_up_at: datetime | None = None,
    ) -> AddFollowUpCommand:
        """フォローアップ記録コマンドへ変換する。"""
        dt = followed_up_at or datetime.now(UTC)
        return AddFollowUpCommand(
            corporate_id=corporate_id,
            record_id=record_id,
            counselor_id=counselor_id,
            followed_up_at=dt,
            method="telephone",
            soap=SoapInput(
                objective=(
                    LabeledNoteInput(text="服薬フォローアップ / 指導料算定受付"),
                ),
            ),
            handbook_status=HandbookStatusInput(presented=True),
            residual_drug=ResidualDrugInput(has_residual_drugs=False),
            information_sheet_provided=False,
        )

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        if " " in full_name:
            parts = full_name.split(" ", 1)
            return parts[0], parts[1]
        if "　" in full_name:
            parts = full_name.split("　", 1)
            return parts[0], parts[1]
        if len(full_name) >= 4:
            return full_name[:2], full_name[2:]
        if len(full_name) >= 2:
            return full_name[:1], full_name[1:]
        return full_name, full_name

    @staticmethod
    def _split_doctor_name(doc_raw: str) -> tuple[str, str]:
        if " " in doc_raw:
            parts = doc_raw.split(" ", 1)
            return parts[0], parts[1]
        if "　" in doc_raw:
            parts = doc_raw.split("　", 1)
            return parts[0], parts[1]
        if len(doc_raw) >= 4 and doc_raw.endswith("医師"):
            return doc_raw[:-2], "医師"
        if len(doc_raw) >= 2:
            return doc_raw[:2], doc_raw[2:] or "医師"
        return doc_raw or "医師", "医師"
