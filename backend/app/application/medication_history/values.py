"""Applicationのvaluesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.application.common.input_normalization import to_optional_text
from app.domain.care_event.identifiers import EventId, EventTypeId
from app.domain.care_event.primitives import EventOccurredTimestamp, EventTypeName
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class MedicationHistoryEventReference:
    """薬歴作成に必要なEventの識別情報。"""

    id: EventId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    event_type_id: EventTypeId
    event_type_standard_code: str | None
    event_type_name: EventTypeName
    occurred_at: EventOccurredTimestamp | None
    reception_id: ReceptionId | None
    prescription_id: PrescriptionId | None
    dispensing_id: DispensingId | None


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value


def parse_enum[E: StrEnum](enum_type: type[E], raw: str, field_name: str) -> E:
    """入力文字列を指定の列挙へ変換する。"""
    try:
        return enum_type(raw)
    except ValueError as exc:
        raise DomainValidationError(f"{field_name}が不正です。") from exc
