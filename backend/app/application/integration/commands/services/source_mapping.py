"""Applicationのsource_mappingを定義する。"""

from __future__ import annotations

from app.application.integration.boundary_models import (
    NsipsAdditionInfo,
    NsipsBundle,
    NsipsDrugSupplementInfo,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsNarcoticInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRemarkInfo,
    NsipsRpInfo,
    NsipsRpUsageSupplementInfo,
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


def map_drug_supplement(value: NsipsDrugSupplementInfo) -> dict[str, object]:
    """薬品補足情報の辞書表現を返す。"""
    return {
        "category_code": value.category_code,
        "text": value.text,
        "supplementary_usage_code": value.supplementary_usage_code,
    }


def map_medicine(value: NsipsMedicineInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "medicine_code": value.medicine_code,
        "medicine_name": value.medicine_name,
        "dosage": value.dosage,
        "unit": value.unit,
        "days_supply": value.days_supply,
        "yj_code": value.yj_code,
        "info_category": value.info_category,
        "drug_code_type": value.drug_code_type,
        "dosage_quantity": value.dosage_quantity,
        "dosage_unit": value.dosage_unit,
        "is_potency": value.is_potency,
        "unit_conversion_factor": value.unit_conversion_factor,
        "uneven_doses": list(value.uneven_doses),
        "supplements": [map_drug_supplement(item) for item in value.supplements],
    }


def map_rp_usage_supplement(value: NsipsRpUsageSupplementInfo) -> dict[str, object]:
    """用法補足情報の辞書表現を返す。"""
    return {
        "category_code": value.category_code,
        "text": value.text,
        "supplementary_usage_code": value.supplementary_usage_code,
        "body_site_code": value.body_site_code,
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
        "dosage_form_code": value.dosage_form_code,
        "dosage_form_name": value.dosage_form_name,
        "usage_code": value.usage_code,
        "daily_frequency": value.daily_frequency,
        "usage_supplements": [
            map_rp_usage_supplement(item) for item in value.usage_supplements
        ],
    }


def map_split(value: NsipsSplitInfo) -> dict[str, object]:
    """受付原本の項目名と値の対応を固定する。"""
    return {
        "iteration": value.iteration,
        "total_split_count": value.total_split_count,
        "split_reason": value.split_reason,
    }


def map_narcotic(value: NsipsNarcoticInfo) -> dict[str, object]:
    """麻薬情報の辞書表現を返す。"""
    return {
        "license_number": value.license_number,
        "patient_address": value.patient_address,
        "patient_phone": value.patient_phone,
    }


def map_remark(value: NsipsRemarkInfo) -> dict[str, object]:
    """処方備考の辞書表現を返す。"""
    return {
        "sequence_number": value.sequence_number,
        "remark_type_code": value.remark_type_code,
        "text": value.text,
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
        "expiration_date": value.expiration_date,
        "narcotic_info": map_narcotic(value.narcotic_info)
        if value.narcotic_info is not None
        else None,
        "remaining_medication_check_code": value.remaining_medication_check_code,
        "refill_total_uses": value.refill_total_uses,
        "remarks": [map_remark(item) for item in value.remarks],
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
        "category": value.category,
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
        "file_name": value.file_name if value.file_name is not None else None,
    }
