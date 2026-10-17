"""薬歴の充足判定に必要な調剤事実の固定値。"""

from dataclasses import dataclass
from datetime import date

from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.medication_history.reference_primitives import DispensingProcessStatus
from app.domain.patient.identifiers import PatientId
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class SubstitutionSource(ValueObject):
    """記録された変更理由。不明はNoneのまま保持する。"""

    reason: str | None


@dataclass(frozen=True, kw_only=True)
class MedicineSource(ValueObject):
    """調剤した薬品の存在と変更記録。"""

    substitution: SubstitutionSource | None


@dataclass(frozen=True, kw_only=True)
class RpSource(ValueObject):
    """剤ごとの数量・薬品の存在と数量調整の有無。"""

    quantity: int
    medicines: tuple[MedicineSource, ...]
    is_quantity_adjusted: bool

    def validate(self) -> None:
        """記録された調剤数量が正であることを保証する。"""
        if self.quantity < 1:
            raise DomainValidationError("調剤数量は1以上で指定してください。")


@dataclass(frozen=True, kw_only=True)
class DispensingSource(ValueObject):
    """同じ対象の調剤事実を、元集約の実装型から独立して保持する。"""

    dispensing_id: DispensingId
    corporate_id: CorporateId
    store_id: StoreId
    patient_id: PatientId
    prescription_id: PrescriptionId
    dispenser_id: StaffId
    status: DispensingProcessStatus
    dispensed_date: date
    dispensed_rps: tuple[RpSource, ...]

    @property
    def substituted_medicines(self) -> tuple[MedicineSource, ...]:
        """変更記録を持つ薬品を列挙する。"""
        return tuple(
            medicine
            for rp in self.dispensed_rps
            for medicine in rp.medicines
            if medicine.substitution is not None
        )
