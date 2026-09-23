"""NSIPS構文解析の中間データ表現。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


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
class NsipsMedicineInfo:
    """NSIPSから抽出した処方薬品明細。"""

    medicine_code: str
    medicine_name: str
    dosage: Decimal
    unit: str


@dataclass(frozen=True, kw_only=True)
class NsipsRpInfo:
    """NSIPSから抽出した剤（Rp）情報。"""

    rp_number: int
    group_name: str
    instructions: str
    dispensing_quantity: int
    medicines: tuple[NsipsMedicineInfo, ...] = ()
    preparation_method: str | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsSplitInfo:
    """NSIPSから抽出した分割調剤情報。"""

    iteration: int
    total_split_count: int
    split_reason: str


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
    """NSIPSから抽出した算定加算情報（レコード08）。"""

    code: str
    name: str
    points: int | None = None
    quantity: int | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsBundle:
    """解析済みの1受付分NSIPSデータ束。"""

    header_version: str
    patient: NsipsPatientInfo
    prescription: NsipsPrescriptionInfo
    dispensed_date: date | None = None
    insurance: NsipsInsuranceInfo | None = None
    additions: tuple[NsipsAdditionInfo, ...] = ()
