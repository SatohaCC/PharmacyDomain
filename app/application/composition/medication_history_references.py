"""MedicationHistoryの参照境界を各Repositoryへ接続する実アダプタ。"""

from __future__ import annotations

from dataclasses import replace

from app.application.common.exceptions import NotFoundError
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
    ReceptionMedicationHistoryBoundary,
    ReceptionMedicationHistorySource,
    StaffQualificationBoundary,
    StatutoryRecordSourceBoundary,
    StoreReferenceBoundary,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingId
from app.domain.dispensing.repository import DispensingProcessRepository
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.value_objects import (
    StatutoryInquiryRecord,
    StatutoryPharmacistName,
    StatutoryRecordSource,
)
from app.domain.patient.primitives import PatientId
from app.domain.patient.repository import PatientRepository
from app.domain.prescription.primitives import PrescriptionId
from app.domain.prescription.repository import PrescriptionRepository
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.repository import ReceptionRepository
from app.domain.staff.primitives import StaffId, StaffQualifications
from app.domain.staff.repository import StaffRepository
from app.domain.store.primitives import StoreId
from app.domain.store.repository import StoreRepository


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
    """調剤セッション集約を取り出す。

    ここだけは他コンテキストの集約そのものを返す。法人・患者・店舗の一致は
    IDでは判定できず、Domain Service が本物の集約を必要とするため。
    """

    def __init__(self, repository: DispensingProcessRepository) -> None:
        self._repository = repository

    async def get_or_raise(
        self,
        *,
        corporate_id: CorporateId,
        dispensing_id: DispensingId,
    ) -> DispensingProcess:
        """未存在・別法人の調剤セッションを、存在を隠す404相当へ畳む。"""
        process = await self._repository.get(
            corporate_id=corporate_id,
            dispensing_id=dispensing_id,
        )
        if process is None:
            raise MedicationHistoryDispensingNotFoundError()
        return process


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


class CounselorQualificationAdapter(StaffQualificationBoundary):
    """スタッフの保有資格だけを取り出し、Staff集約は渡さない。"""

    def __init__(self, repository: StaffRepository) -> None:
        self._repository = repository

    async def get_qualifications(
        self,
        *,
        corporate_id: CorporateId,
        staff_id: StaffId,
    ) -> StaffQualifications:
        """未存在・別法人のスタッフを404相当へ畳み、資格をそのまま返す。

        薬剤師かどうかの判定は ``CounselorQualificationService`` の責務であり、
        ここでは行わない。資格が空でも在籍しているので例外にしない。
        """
        staff = await self._repository.get(
            corporate_id=corporate_id,
            staff_id=staff_id,
        )
        if staff is None:
            raise MedicationHistoryStaffNotFoundError()
        return staff.qualifications


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
            patient_birth_date=patient.birth_date,
            pharmacist_names=await self._pharmacist_names(
                corporate_id=corporate_id, staff_ids=staff_ids
            ),
            prescription_id=prescription.id,
            prescription_issued_date=prescription.period.issued_date,
            prescriber_names=prescription.prescriber.names,
            medical_institution_name=prescription.medical_institution.name,
            medical_institution_address=prescription.medical_institution.address,
            inquiries=tuple(
                StatutoryInquiryRecord(
                    inquiry_number=inquiry.inquiry_number,
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
