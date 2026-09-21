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
    gender: str
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
    rps: tuple[NsipsRpInfo, ...] = field(default_factory=tuple)
    split_info: NsipsSplitInfo | None = None


@dataclass(frozen=True, kw_only=True)
class NsipsBundle:
    """解析済みの1受付分NSIPSデータ束。"""

    header_version: str
    patient: NsipsPatientInfo
    prescription: NsipsPrescriptionInfo
