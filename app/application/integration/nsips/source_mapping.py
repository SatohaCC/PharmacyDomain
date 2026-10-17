"""NSIPS原本を保存形式へ明示的に変換する。"""

from app.application.integration.nsips.models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
    NsipsSplitInfo,
)


def map_patient(value: NsipsPatientInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "external_patient_id": value.external_patient_id,
        "kanji_name": value.kanji_name,
        "kana_name": value.kana_name,
        "birth_date": value.birth_date,
        "gender": value.gender if value.gender is not None else None,
        "postal_code": value.postal_code if value.postal_code is not None else None,
        "address": value.address if value.address is not None else None,
        "phone_number": value.phone_number if value.phone_number is not None else None,
    }


def map_medicine(value: NsipsMedicineInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "medicine_code": value.medicine_code,
        "medicine_name": value.medicine_name,
        "dosage": value.dosage,
        "unit": value.unit,
    }


def map_rp(value: NsipsRpInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "rp_number": value.rp_number,
        "group_name": value.group_name,
        "instructions": value.instructions,
        "dispensing_quantity": value.dispensing_quantity,
        "medicines": [map_medicine(item) for item in value.medicines],
        "preparation_method": value.preparation_method
        if value.preparation_method is not None
        else None,
    }


def map_split(value: NsipsSplitInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "iteration": value.iteration,
        "total_split_count": value.total_split_count,
        "split_reason": value.split_reason,
    }


def map_prescription(value: NsipsPrescriptionInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "document_number": value.document_number,
        "issued_date": value.issued_date,
        "institution_code": value.institution_code,
        "institution_name": value.institution_name,
        "department_code": value.department_code
        if value.department_code is not None
        else None,
        "department_name": value.department_name
        if value.department_name is not None
        else None,
        "doctor_name": value.doctor_name,
        "institution_prefecture_code": value.institution_prefecture_code
        if value.institution_prefecture_code is not None
        else None,
        "doctor_kana": value.doctor_kana if value.doctor_kana is not None else None,
        "rps": [map_rp(item) for item in value.rps],
        "split_info": map_split(value.split_info)
        if value.split_info is not None
        else None,
    }


def map_insurance(value: NsipsInsuranceInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "insurer_number": value.insurer_number,
        "insured_symbol": value.insured_symbol,
        "insured_number": value.insured_number,
        "branch_number": value.branch_number
        if value.branch_number is not None
        else None,
        "insured_type": value.insured_type if value.insured_type is not None else None,
        "benefit_ratio": value.benefit_ratio
        if value.benefit_ratio is not None
        else None,
        "public_payer_number_1": value.public_payer_number_1
        if value.public_payer_number_1 is not None
        else None,
        "public_recipient_number_1": value.public_recipient_number_1
        if value.public_recipient_number_1 is not None
        else None,
        "public_payer_number_2": value.public_payer_number_2
        if value.public_payer_number_2 is not None
        else None,
        "public_recipient_number_2": value.public_recipient_number_2
        if value.public_recipient_number_2 is not None
        else None,
    }


def map_addition(value: NsipsAdditionInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "code": value.code,
        "name": value.name,
        "points": value.points if value.points is not None else None,
        "quantity": value.quantity if value.quantity is not None else None,
    }


def map_bundle(value: NsipsBundle) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "header_version": value.header_version,
        "patient": map_patient(value.patient),
        "prescription": map_prescription(value.prescription),
        "dispensed_date": value.dispensed_date
        if value.dispensed_date is not None
        else None,
        "insurance": map_insurance(value.insurance)
        if value.insurance is not None
        else None,
        "additions": [map_addition(item) for item in value.additions],
        "correction_kind": value.correction_kind
        if value.correction_kind is not None
        else None,
    }
