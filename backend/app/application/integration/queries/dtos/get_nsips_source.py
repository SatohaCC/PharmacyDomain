"""ApplicationのNSIPS原本DTOを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class NsipsSourceMedicineDto:
    """原本の薬品情報。"""

    medicine_code: str
    medicine_name: str
    dosage: str
    unit: str


@dataclass(frozen=True, kw_only=True)
class NsipsSourceRpDto:
    """原本のRp処方情報。"""

    rp_number: int
    group_name: str
    instructions: str
    dispensing_quantity: int
    medicines: tuple[NsipsSourceMedicineDto, ...]
    preparation_method: str | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsSourcePrescriptionDto:
    """原本の処方箋記載事項。"""

    document_number: str
    issued_date: str
    institution_code: str
    institution_name: str
    department_code: str | None = None
    department_name: str | None = None
    doctor_name: str
    institution_prefecture_code: str | None = None
    doctor_kana: str | None = None
    rps: tuple[NsipsSourceRpDto, ...] = ()


@dataclass(frozen=True, kw_only=True)
class NsipsSourceInsuranceDto:
    """原本の保険情報。"""

    insurer_number: str
    insured_symbol: str
    insured_number: str
    branch_number: str | None = None
    insured_type: str | None = None
    benefit_ratio: int | None = None
    public_payer_number_1: str | None = None
    public_recipient_number_1: str | None = None
    public_payer_number_2: str | None = None
    public_recipient_number_2: str | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsSourceAdditionDto:
    """原本の算定加算情報。"""

    code: str
    name: str
    points: int | None = None
    quantity: int | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsSourceCorrectionDto:
    """原本の訂正履歴情報。"""

    fingerprint: str
    changed_fields: tuple[str, ...]
    received_at: str


@dataclass(frozen=True, kw_only=True)
class NsipsSourceDto:
    """NSIPS原本照会DTO。"""

    reception_id: str
    corporate_id: str
    store_id: str
    patient_id: str
    source_fingerprint: str
    source_status: str
    imported_at: str
    prescription: NsipsSourcePrescriptionDto | None = None
    dispensed_date: str | None = None
    insurance: NsipsSourceInsuranceDto | None = None
    additions: tuple[NsipsSourceAdditionDto, ...] = ()
    correction_history: tuple[NsipsSourceCorrectionDto, ...] = ()
    event_id: str | None = None
    medication_history_id: str | None = None
    prescription_id: str | None = None
    dispensing_id: str | None = None
    has_pending_correction_review: bool = False
