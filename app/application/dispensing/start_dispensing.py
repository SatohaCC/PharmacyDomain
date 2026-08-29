"""調剤セッションを開始するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.dispensing.exceptions import (
    PrescriptionNotReadyForDispensingError,
)
from app.application.dispensing.get_dispensing import DispensingProcessDto
from app.application.dispensing.inputs import DispensedRpInput
from app.application.dispensing.reference import (
    PrescriptionReferenceBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.application.dispensing.support import (
    build_dispensed_rps,
    parse_enum,
    to_optional_text,
)
from app.base.application.clock import Clock
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensedDate,
    DispensingConsistencyService,
    DispensingIteration,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
    DispensingProcess,
    DispensingProcessRepository,
    DispensingSplitReason,
    DispensingTimestamp,
)
from app.domain.prescription.primitives import PrescriptionId, PrescriptionStatus
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class StartDispensingCommand:
    """調剤セッション開始の入力データ。開始日時は含めない。"""

    corporate_id: str
    store_id: str
    prescription_id: str
    dispenser_id: str
    iteration: int
    dispensed_date: date
    dispensed_rps: tuple[DispensedRpInput, ...]
    split_reason: str | None = None


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
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_DISPENSING,
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id,
            store_id=store_id,
        )
        prescription_id = PrescriptionId.parse(command.prescription_id)
        prescription = await self._prescription_reference.get_or_raise(
            corporate_id=corporate_id,
            prescription_id=prescription_id,
        )
        self._ensure_prescription_is_ready(prescription.status)

        dispenser_id = StaffId.parse(command.dispenser_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=dispenser_id,
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
        )
        existing = await self._repository.list_by_prescription(
            corporate_id=corporate_id,
            prescription_id=prescription_id,
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


def _find_previous(
    existing: list[DispensingProcess], iteration: int
) -> DispensingProcess | None:
    """直前の回のセッションを探す。

    他薬局で実施された回は自局のRepositoryに無いため ``None`` になりうる。
    そのときに検証を飛ばすか拒否するかは Domain Service 側の判断
    （``PreviousDispensingUnknownError`` として拒否する）。
    """
    for item in existing:
        if item.iteration.value == iteration - 1:
            return item
    return None
