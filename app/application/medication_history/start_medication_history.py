"""服薬指導の記録を下書きとして起こすユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import (
    HandbookStatusInput,
    ProfileUpdateInput,
    ResidualDrugInput,
    SoapInput,
)
from app.application.medication_history.reference import (
    DispensingReferenceBoundary,
    StaffQualificationBoundary,
    StoreReferenceBoundary,
)
from app.application.medication_history.support import (
    build_handbook_status,
    build_profile_updates,
    build_residual_drug,
    build_soap,
    parse_enum,
)
from app.base.application.clock import Clock
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history import (
    CounselingMethod,
    CounselingTimestamp,
    CounselorQualificationService,
    MedicationHistoryRecord,
    MedicationHistoryRepository,
)
from app.domain.staff.primitives import StaffId
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class StartMedicationHistoryCommand:
    """薬歴作成の入力データ。指導日時は含めない。"""

    corporate_id: str
    store_id: str
    dispensing_id: str
    counselor_id: str
    method: str
    soap: SoapInput
    handbook_status: HandbookStatusInput
    residual_drug: ResidualDrugInput
    information_sheet_provided: bool = False
    profile_updates: ProfileUpdateInput | None = None


class StartMedicationHistoryUseCase:
    """調剤セッションとの一致と指導者の資格を確認して薬歴を起こす。"""

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
        store_reference: StoreReferenceBoundary,
        dispensing_reference: DispensingReferenceBoundary,
        staff_qualification: StaffQualificationBoundary,
        counselor_service: CounselorQualificationService,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._dispensing_reference = dispensing_reference
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._clock = clock

    async def execute(
        self, command: StartMedicationHistoryCommand
    ) -> MedicationHistoryDto:
        """境界と集約外の不変条件を確認して下書きを保存する。

        **患者・処方箋は調剤セッションから決まる。** Commandで受け取ると、調剤と
        食い違う薬歴を作れてしまう。ここから取る限り調剤との一致は
        **構築の形で保証される**ので、判定を重ねて置かない。

        指導日時はCommandではなく注入Clockから採る。呼び出し元が過去日時を
        詐称できないようにするため（AGENTS.md「資格の時間境界」と同じ理由）。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        store_id = StoreId.parse(command.store_id)
        await self._store_reference.require_exists(
            corporate_id=corporate_id, store_id=store_id
        )
        dispensing = await self._dispensing_reference.get_or_raise(
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(command.dispensing_id),
        )
        counselor_id = StaffId.parse(command.counselor_id)
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=counselor_id
        )
        self._counselor_service.ensure_pharmacist(qualifications)

        record = MedicationHistoryRecord.start(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=dispensing.patient_id,
            dispensing_id=dispensing.id,
            prescription_id=dispensing.prescription_id,
            counselor_id=counselor_id,
            counseled_at=CounselingTimestamp(self._clock.now()),
            method=parse_enum(CounselingMethod, command.method, "服薬指導の方法"),
            soap=build_soap(command.soap),
            handbook_status=build_handbook_status(command.handbook_status),
            residual_drug=build_residual_drug(command.residual_drug),
            information_sheet_provided=command.information_sheet_provided,
            profile_updates=build_profile_updates(command.profile_updates),
        )
        await self._repository.save(record)
        return MedicationHistoryDto.from_entity(record)
