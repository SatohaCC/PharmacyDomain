"""MedicationHistoryの参照境界を各Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.application.common.exceptions import NotFoundError
from app.application.composition.medication_history_snapshot_mapping import (
    dispensing_source,
)
from app.application.composition.reference_support import load_store_in_corporate
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryPatientNotFoundError,
    MedicationHistoryPrescriptionNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
)
from app.application.medication_history.inputs import BillingAdditionInput
from app.application.medication_history.reference import (
    DispensingReferenceBoundary,
    MedicationHistoryEventOccurrenceBoundary,
    ReceptionMedicationHistoryBoundary,
    ReceptionMedicationHistorySource,
    StaffQualificationBoundary,
    StatutoryRecordSourceBoundary,
    StoreReferenceBoundary,
)
from app.domain.care_event.identifiers import EventId
from app.domain.care_event.primitives import EventOccurredTimestamp
from app.domain.care_event.repositories import EventRepository
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.identifiers import DispensingId
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.identifiers import MedicationHistoryRecordId
from app.domain.medication_history.primitives import (
    InquiryNumber,
    MedicalInstitutionAddressLine,
    MedicalInstitutionName,
    PatientBirthDate,
    PrescriptionIssuedDate,
)
from app.domain.medication_history.value_objects import (
    DispensingSource,
    PharmacistQualification,
    StatutoryInquiryRecord,
    StatutoryPharmacistName,
    StatutoryRecordSource,
)
from app.domain.patient.identifiers import PatientId
from app.domain.patient.repositories import PatientRepository
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.repositories import PrescriptionRepository
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.repositories import ReceptionRepository
from app.domain.staff.identifiers import StaffId
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.value_objects import PharmacistProfile
from app.domain.store.identifiers import StoreId
from app.domain.store.repositories import StoreRepository


class MedicationHistoryStoreReferenceAdapter(StoreReferenceBoundary):
    """店舗の存在と法人境界だけを確認し、店舗集約は渡さない。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def require_exists(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
    ) -> None:
        """未存在・別法人の店舗を、存在を隠す404相当へ畳む。"""
        store = await load_store_in_corporate(
            self._repository,
            corporate_id=corporate_id,
            store_id=store_id,
        )
        if store is None:
            raise MedicationHistoryStoreNotFoundError()


class DispensingSourceAdapter(DispensingReferenceBoundary):
    """調剤Repositoryの記録を薬歴が必要とする固定値へ変換する。"""

    def __init__(self, repository: DispensingProcessRepository) -> None:
        self._repository = repository

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingSource:
        """未存在・別法人の調剤セッションを、存在を隠す404相当へ畳む。"""
        process = await self._repository.get(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
        )
        if process is None:
            raise MedicationHistoryDispensingNotFoundError()
        return dispensing_source(process)


class ReceptionMedicationHistorySourceAdapter(ReceptionMedicationHistoryBoundary):
    """Receptionから受信由来情報を読み、初回保存後の関連を記録する。"""

    def __init__(self, repository: ReceptionRepository) -> None:
        self._repository = repository

    async def get_for_initial_save(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: str,
    ) -> ReceptionMedicationHistorySource | None:
        """Receptionを薬歴へ渡す項目だけのProjectionに畳む。"""
        reception = await self._repository.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=ReceptionId.parse(reception_id),
        )
        if reception is None:
            return None
        source_data = reception.source_data
        return ReceptionMedicationHistorySource(
            patient_id=reception.patient_id,
            prescription_id=reception.prescription_id,
            dispensing_id=reception.dispensing_id,
            event_id=reception.event_id,
            medication_history_id=reception.medication_history_id,
            source_system="NSIPS" if source_data is not None else None,
            imported_at=source_data.imported_at if source_data is not None else None,
            is_follow_up=(
                source_data.is_follow_up if source_data is not None else False
            ),
            billing_additions=(
                tuple(
                    BillingAdditionInput(
                        code=item.code,
                        name=item.name,
                        points=item.points,
                        quantity=item.quantity,
                    )
                    for item in source_data.billing_additions
                )
                if source_data is not None
                else ()
            ),
        )

    async def associate_medication_history(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        reception_id: str,
        medication_history_id: MedicationHistoryRecordId,
    ) -> None:
        """初回保存した薬歴への受付リンクを保存する。"""
        parsed_reception_id = ReceptionId.parse(reception_id)
        reception = await self._repository.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=parsed_reception_id,
        )
        if reception is None:
            raise NotFoundError(
                "指定された受付が見つかりません。", code="RECEPTION_NOT_FOUND"
            )
        if (
            reception.medication_history_id is not None
            and reception.medication_history_id != medication_history_id
        ):
            raise DomainValidationError(
                "受付は別の薬歴に関連付いているため、付け替えできません。"
            )
        await self._repository.save(
            replace(reception, medication_history_id=medication_history_id)
        )


class MedicationHistoryEventOccurrenceAdapter(MedicationHistoryEventOccurrenceBoundary):
    """Event Repositoryを使い、時刻不明のEventだけ発生日時を確定する。"""

    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    async def resolve_unknown_occurrence(
        self,
        *,
        corporate_id: CorporateId,
        event_id: EventId,
        occurred_at: datetime | None,
    ) -> None:
        event = await self._repository.get(
            corporate_id=corporate_id,
            event_id=event_id,
        )
        if event is None:
            raise MedicationHistoryDomainError("薬歴に関連するEventが見つかりません。")
        if event.occurred_at is None:
            if occurred_at is None:
                raise MedicationHistoryDomainError(
                    "時刻不明のEventを含む薬歴の確定には、確認済みの発生日時が必要です。"
                )
            await self._repository.save(
                event.resolve_unknown_occurrence(EventOccurredTimestamp(occurred_at))
            )
            return
        if occurred_at is not None:
            raise MedicationHistoryDomainError(
                "登録済みのEvent発生日時は変更できません。"
            )


class CounselorQualificationAdapter(StaffQualificationBoundary):
    """スタッフの保有資格だけを取り出し、Staff集約は渡さない。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> PharmacistQualification:
        """未存在・別法人のスタッフを404相当へ畳み、利用側の資格保有事実へ変換する。

        薬剤師かどうかの判定は ``CounselorQualificationService`` の責務であり、
        ここでは行わない。資格が空でも在籍しているので例外にしない。
        """
        staff = await self._repository.get(
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        if staff is None:
            raise MedicationHistoryStaffNotFoundError()
        return PharmacistQualification(
            has_pharmacist=staff.qualifications.has(PharmacistProfile)
        )


class StatutoryRecordSourceAdapter(StatutoryRecordSourceBoundary):
    """調剤録の記載事項のうち、薬歴から読めない事実を各Repositoryから集める。

    患者集約・処方箋集約そのものは渡さない。薬歴ドメインからそれらを import
    できないのは設計上の禁止であり、ここで不変スナップショットへ畳む。
    """

    def __init__(
        self,
        patients: PatientRepository,
        prescriptions: PrescriptionRepository,
        staffs: StaffRepository,
    ) -> None:
        self._patients = patients
        self._prescriptions = prescriptions
        self._staffs = staffs

    async def build(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        prescription_id: PrescriptionId,
        staff_ids: frozenset[StaffId],
    ) -> StatutoryRecordSource:
        """記載事項のスナップショットを組み立てる。

        未存在・別法人の患者と処方箋は404相当へ畳む。**スタッフだけは畳まない。**
        氏名を引けないこと自体が「氏名を記載できない」という判定材料であり、
        例外にすると、その薬歴について何も報告できなくなる。
        """
        patient = await self._patients.get(
            corporate_id=corporate_id, patient_id=patient_id
        )
        if patient is None:
            raise MedicationHistoryPatientNotFoundError()
        prescription = await self._prescriptions.get(
            corporate_id=corporate_id, prescription_id=prescription_id
        )
        if prescription is None:
            raise MedicationHistoryPrescriptionNotFoundError()
        return StatutoryRecordSource(
            patient_id=patient.id,
            patient_names=patient.names,
            patient_birth_date=PatientBirthDate(patient.birth_date.value)
            if patient.birth_date is not None
            else None,
            pharmacist_names=await self._pharmacist_names(
                corporate_id=corporate_id, staff_ids=staff_ids
            ),
            prescription_id=prescription.id,
            prescription_issued_date=PrescriptionIssuedDate(
                prescription.period.issued_date.value
            ),
            prescriber_names=prescription.prescriber.names,
            medical_institution_name=MedicalInstitutionName(
                prescription.medical_institution.name.value
            ),
            medical_institution_address=MedicalInstitutionAddressLine(
                prescription.medical_institution.address.value
            )
            if prescription.medical_institution.address is not None
            else None,
            inquiries=tuple(
                StatutoryInquiryRecord(
                    inquiry_number=InquiryNumber(inquiry.inquiry_number.value),
                    has_response=not inquiry.is_open,
                )
                for inquiry in prescription.inquiries
            ),
        )

    async def _pharmacist_names(
        self,
        *,
        corporate_id: CorporateId,
        staff_ids: frozenset[StaffId],
    ) -> tuple[StatutoryPharmacistName, ...]:
        """氏名を引けたスタッフだけを返す。引けなかった分は落とす。"""
        resolved: list[StatutoryPharmacistName] = []
        for staff_id in sorted(staff_ids, key=lambda value: value.value):
            staff = await self._staffs.get(corporate_id=corporate_id, staff_id=staff_id)
            if staff is None:
                continue
            resolved.append(
                StatutoryPharmacistName(staff_id=staff_id, names=staff.names)
            )
        return tuple(resolved)
