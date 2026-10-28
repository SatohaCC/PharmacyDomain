"""Applicationのmodelsを定義する。"""

from __future__ import annotations

_SUPPORTED_RAW_NSIPS_VERSIONS: frozenset[str] = frozenset()
_PATIENT_PROFILE_FIELD_PATHS = (
    "patient.kanji_name",
    "patient.kana_name",
    "patient.birth_date",
    "patient.gender",
    "patient.postal_code",
    "patient.address",
    "patient.phone_number",
)
_OPTIONAL_PATIENT_PROFILE_FIELD_PATHS = frozenset(
    {"patient.gender", "patient.postal_code", "patient.address", "patient.phone_number"}
)
_PATIENT_PROFILE_CONFLICT_NAMES = {
    "patient.gender": "gender",
    "patient.postal_code": "postal_code",
    "patient.address": "address",
    "patient.phone_number": "phone_number",
}
_EXTERNAL_PATIENT_ID_FIELD_PATH = "patient.external_patient_id"
