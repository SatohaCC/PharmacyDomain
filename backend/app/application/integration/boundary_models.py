"""Applicationのvaluesを定義する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.domain.corporate.identifiers import CorporateId
from app.domain.reception.identifiers import ReceptionId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class _PatientProfileApplication:
    """今回の受信で記録した項目と実際に更新した項目。"""

    conflicts: tuple[str, ...] = ()
    updated_fields: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class NsipsPatientInfo:
    """NSIPSから抽出した患者情報。"""

    external_patient_id: str
    kanji_name: str
    kana_name: str
    birth_date: date
    gender: str | None
    postal_code: str | None = None
    address: str | None = None
    phone_number: str | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsDrugSupplementInfo:
    """NSIPSから抽出した薬品補足情報。"""

    category_code: str
    text: str
    supplementary_usage_code: str = ""


@dataclass(frozen=True, kw_only=True)
class NsipsRpUsageSupplementInfo:
    """NSIPSから抽出した剤（Rp）用法補足情報。"""

    category_code: str
    text: str
    supplementary_usage_code: str = ""
    body_site_code: str = ""


@dataclass(frozen=True, kw_only=True)
class NsipsMedicineInfo:
    """NSIPSから抽出した処方薬品明細。"""

    medicine_code: str
    medicine_name: str
    dosage: Decimal
    unit: str
    days_supply: int | None = None
    yj_code: str = ""
    info_category: str = "drug"
    drug_code_type: str = ""
    dosage_quantity: Decimal | None = None
    dosage_unit: str = ""
    is_potency: bool = False
    unit_conversion_factor: Decimal | None = None
    uneven_doses: tuple[Decimal | None, ...] = ()
    supplements: tuple[NsipsDrugSupplementInfo, ...] = ()


@dataclass(frozen=True, kw_only=True)
class NsipsRpInfo:
    """NSIPSから抽出した剤（Rp）情報。"""

    rp_number: int
    group_name: str
    instructions: str
    dispensing_quantity: int
    medicines: tuple[NsipsMedicineInfo, ...] = ()
    preparation_method: str | None = None
    dosage_form_code: str = ""
    dosage_form_name: str = ""
    usage_code: str = ""
    daily_frequency: int | None = None
    usage_supplements: tuple[NsipsRpUsageSupplementInfo, ...] = ()


@dataclass(frozen=True, kw_only=True)
class NsipsSplitInfo:
    """NSIPSから抽出した分割調剤情報。"""

    iteration: int
    total_split_count: int
    split_reason: str


@dataclass(frozen=True, kw_only=True)
class NsipsNarcoticInfo:
    """NSIPSから抽出した麻薬施用情報。"""

    license_number: str
    patient_address: str
    patient_phone: str


@dataclass(frozen=True, kw_only=True)
class NsipsRemarkInfo:
    """NSIPSから抽出した備考情報。"""

    sequence_number: int
    remark_type_code: str = ""
    text: str


@dataclass(frozen=True, kw_only=True)
class NsipsPrescriptionInfo:
    """NSIPSから抽出した処方基本情報。"""

    document_number: str
    issued_date: date
    institution_code: str
    institution_name: str
    department_code: str | None
    department_name: str | None
    doctor_name: str
    institution_prefecture_code: str | None = None
    doctor_kana: str | None = None
    rps: tuple[NsipsRpInfo, ...] = field(default_factory=tuple)
    split_info: NsipsSplitInfo | None = None
    expiration_date: date | None = None
    narcotic_info: NsipsNarcoticInfo | None = None
    remaining_medication_check_code: str = ""
    refill_total_uses: int | None = None
    remarks: tuple[NsipsRemarkInfo, ...] = ()


@dataclass(frozen=True, kw_only=True)
class NsipsInsuranceInfo:
    """NSIPSから抽出した保険・公費情報（レコード03）。"""

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
class NsipsAdditionInfo:
    """NSIPSから抽出した算定加算情報（レコード08または算定点数）。"""

    code: str
    name: str
    points: int | None = None
    quantity: int | None = None
    category: str = "addition"


class NsipsOperation(StrEnum):
    """NSIPSファイルが要求している操作。ファイル名から判定する。"""

    CREATE = "create"
    """新規の調剤内容の登録。Bファイルの初回受信も含む。"""

    UPDATE = "update"
    """登録済みの調剤内容の訂正。"""

    DELETE = "delete"
    """登録済みの調剤内容の取り消し。"""


class NsipsFileStatus(StrEnum):
    """台帳から見た1ファイルの取込状態。"""

    PENDING = "pending"
    """受信済み。まだ適用していない。"""

    APPLIED = "applied"
    """薬歴への反映が完了した。"""

    FAILED = "failed"
    """適用を試みて失敗した。error_text に理由が入る。"""


@dataclass(frozen=True, kw_only=True)
class NsipsFileRecord:
    """受信した1つのNSIPSファイルの台帳エントリ。"""

    id: UUID
    corporate_id: CorporateId
    store_id: StoreId
    file_id: str
    file_name: str
    operation: NsipsOperation
    status: NsipsFileStatus
    received_at: datetime
    raw_payload: str = ""
    target_reception_id: ReceptionId | None = None
    processed_at: datetime | None = None
    error_text: str = ""


@dataclass(frozen=True, kw_only=True)
class NsipsBundle:
    """解析済みの1受付分NSIPSデータ束。"""

    header_version: str
    patient: NsipsPatientInfo
    prescription: NsipsPrescriptionInfo
    dispensed_date: date | None = None
    insurance: NsipsInsuranceInfo | None = None
    additions: tuple[NsipsAdditionInfo, ...] = ()
    correction_kind: str | None = None
    file_name: str | None = None
