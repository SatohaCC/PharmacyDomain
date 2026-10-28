"""参照投影に必要な判定材料の選択とDomainサービスの呼び出し。"""

from app.application.medication_history.queries.dtos.verify_statutory_record import (
    StatutoryRecordSufficiencyDto,
)
from app.domain.dispensing.identifiers import DispensingId
from app.domain.medication_history.entities import MedicationHistoryRecord
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.services import StatutoryDispensingRecordService
from app.domain.medication_history.value_objects import (
    DispensingSource,
    StatutoryRecordSource,
)
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.staff.identifiers import StaffId


class StatutoryProjectionService:
    """業務判定を読取アダプタへ漏らさず、公開用の不変な結果へ移す。"""

    def __init__(self, service: StatutoryDispensingRecordService) -> None:
        self._service = service

    @staticmethod
    def references(
        record: MedicationHistoryRecord,
    ) -> tuple[DispensingId, PrescriptionId]:
        """処方箋受付Eventに関連する薬歴に限って参照元を決める。"""
        if record.dispensing_id is None or record.prescription_id is None:
            raise MedicationHistoryDomainError(
                "調剤録の代替確認は処方箋受付Eventに関連する薬歴だけで行えます。"
            )
        return (record.dispensing_id, record.prescription_id)

    @staticmethod
    def staff_ids(
        record: MedicationHistoryRecord, dispensing: DispensingSource
    ) -> frozenset[StaffId]:
        """調剤者と指導者だけを照会対象とし、最終鑑査者は含めない。"""
        identifiers = {dispensing.dispenser_id}
        counselor_id = record.effective_facts.counselor_id
        if counselor_id is not None:
            identifiers.add(counselor_id)
        return frozenset(identifiers)

    def project(
        self,
        record: MedicationHistoryRecord,
        dispensing: DispensingSource,
        source: StatutoryRecordSource,
    ) -> StatutoryRecordSufficiencyDto:
        """Domain判定結果を公開DTOへ変換する。"""
        dispensing_id, prescription_id = self.references(record)
        return StatutoryRecordSufficiencyDto.from_value(
            self._service.verify(record, dispensing, source),
            record_id=str(record.id.value),
            dispensing_id=str(dispensing_id.value),
            prescription_id=str(prescription_id.value),
        )
