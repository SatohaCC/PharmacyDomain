"""調剤の事実を薬歴が必要とする不変情報へ変換する。"""

from app.domain.dispensing.entities import DispensingProcess
from app.domain.medication_history.primitives import (
    DispensingProcessStatus,
    SourceDispensingQuantity,
    SourceSubstitutionReason,
)
from app.domain.medication_history.value_objects import (
    DispensingSource,
    MedicineSource,
    RpSource,
    SubstitutionSource,
)


def dispensing_source(value: DispensingProcess) -> DispensingSource:
    """対象の同一性と記載事項の判断材料を明示的に写す。"""
    return DispensingSource(
        dispensing_id=value.id,
        corporate_id=value.corporate_id,
        store_id=value.store_id,
        patient_id=value.patient_id,
        prescription_id=value.prescription_id,
        dispenser_id=value.dispenser_id,
        status=DispensingProcessStatus(value.status.value),
        dispensed_date=value.dispensed_date.value,
        dispensed_rps=tuple(
            RpSource(
                quantity=SourceDispensingQuantity(rp.quantity.value),
                is_quantity_adjusted=rp.is_quantity_adjusted,
                medicines=tuple(
                    MedicineSource(
                        substitution=SubstitutionSource(
                            reason=(
                                SourceSubstitutionReason(
                                    medicine.substitution.reason.value
                                )
                                if medicine.substitution.reason is not None
                                else None
                            )
                        )
                        if medicine.substitution is not None
                        else None
                    )
                    for medicine in rp.medicines
                ),
            )
            for rp in value.dispensed_rps
        ),
    )
