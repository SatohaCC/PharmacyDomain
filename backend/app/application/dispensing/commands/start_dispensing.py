"""Applicationのstart_dispensingを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.common.input_normalization import to_optional_text
from app.application.dispensing.commands.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.commands.models import StartDispensingCommand
from app.application.dispensing.commands.services.start_dispensing import _find_previous
from app.application.dispensing.commands.services.support import (
    build_dispensed_rps,
    resolve_acting_staff_id,
)
from app.application.dispensing.errors import (
    DispensingDateRequiredError,
    PrescriptionNotReadyForDispensingError,
)
from app.application.dispensing.interfaces.references import (
    PrescriptionReferenceBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.application.dispensing.values import parse_enum
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.entities import DispensingProcess
from app.domain.dispensing.primitives import (
    DispensedDate,
    DispensingIteration,
    DispensingSplitReason,
    DispensingTimestamp,
    PrescriptionStatus,
    TotalSplitCount,
)
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.dispensing.services import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.store.identifiers import StoreId


class StartDispensingUseCase:
    """処方箋・担当者・前回セッションとの整合を確認して調剤を開始する。"""

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        prescription_reference: PrescriptionReferenceBoundary,
        staff_qualification: StaffQualificationBoundary,
        consistency_service: DispensingConsistencyService,
        pharmacist_service: DispensingPharmacistService,
        uniqueness_service: DispensingIterationUniquenessService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._prescription_reference = prescription_reference
        self._staff_qualification = staff_qualification
        self._consistency_service = consistency_service
        self._pharmacist_service = pharmacist_service
        self._uniqueness_service = uniqueness_service
        self._clock = clock

    async def execute(self, command: StartDispensingCommand) -> DispensingProcessDto:
        """境界と集約外の不変条件を確認して調剤セッションを保存する。"""
        if command.dispensed_date is None:
            raise DispensingDateRequiredError()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_DISPENSING
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id, store_id=store_id
        )
        prescription_id = PrescriptionId.parse(command.prescription_id)
        prescription = await self._prescription_reference.get_or_raise(
            corporate_id=corporate_id, prescription_id=prescription_id
        )
        self._ensure_prescription_is_ready(prescription.status)
        dispenser_id = resolve_acting_staff_id(
            self._corporate_access.actor, command.dispenser_id
        )
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=dispenser_id,
            store_id=store_id,
            as_of=business_date(self._clock),
        )
        self._pharmacist_service.ensure_dispenser(qualifications)
        process = DispensingProcess.start(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=prescription.patient_id,
            prescription_id=prescription_id,
            iteration=DispensingIteration(command.iteration),
            dispensed_date=DispensedDate(command.dispensed_date),
            dispenser_id=dispenser_id,
            started_at=DispensingTimestamp(self._clock.now()),
            dispensed_rps=build_dispensed_rps(command.dispensed_rps),
            split_reason=self._parse_split_reason(command.split_reason),
            total_split_count=TotalSplitCount(command.total_split_count)
            if command.total_split_count is not None
            else None,
        )
        existing = await self._repository.list_by_prescription(
            corporate_id=corporate_id, prescription_id=prescription_id
        )
        self._uniqueness_service.ensure_no_conflict(process, existing)
        self._consistency_service.ensure_consistent(
            process,
            prescription,
            previous=_find_previous(existing, process.iteration.value),
        )
        await self._repository.save(process)
        return DispensingProcessDto.from_entity(process)

    @staticmethod
    def _parse_split_reason(raw: str | None) -> DispensingSplitReason | None:
        """分割理由を変換する。空文字は未指定として扱う。"""
        value = to_optional_text(raw)
        if value is None:
            return None
        return parse_enum(DispensingSplitReason, value, "分割調剤の理由")

    @staticmethod
    def _ensure_prescription_is_ready(status: PrescriptionStatus) -> None:
        """処方内容が確定していることを確認する。

        「未回答の疑義照会があるか」は処方箋集約が判定済みで、それが
        ``READY_FOR_DISPENSING`` という状態に畳まれている。ここで
        ``has_open_inquiry`` を再度見ると、同じ規則が2箇所に分かれる。
        """
        if status is not PrescriptionStatus.READY_FOR_DISPENSING:
            raise PrescriptionNotReadyForDispensingError()
