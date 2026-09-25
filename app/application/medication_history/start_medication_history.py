"""服薬指導の記録を下書きとして起こすユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.optional_conversion import build_optional
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import (
    BillingAdditionInput,
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
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    BillingAdditionCode,
    BillingAdditionName,
    CounselingMethod,
    CounselingTimestamp,
    MedicationHistoryImportTimestamp,
    MedicationHistorySourceSystem,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import BillingAddition
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class StartMedicationHistoryCommand:
    """薬歴作成の入力データ。指導日時は含めない。"""

    corporate_id: str
    store_id: str
    dispensing_id: str
    method: str | None
    soap: SoapInput
    handbook_status: HandbookStatusInput | None
    residual_drug: ResidualDrugInput | None
    information_sheet_provided: bool | None = None
    profile_updates: ProfileUpdateInput | None = None
    billing_additions: tuple[BillingAdditionInput, ...] | None = None
    source_system: str | None = None


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

        通常起票の指導者は信頼済みActorから決め、指導日時はClockから採る。
        NSIPS由来の起票は受信時刻だけを記録し、指導実績を作らない。
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
        is_nsips_import = command.source_system == "NSIPS"
        if is_nsips_import:
            counselor_id = None
            counseled_at = None
            imported_at = MedicationHistoryImportTimestamp(self._clock.now())
        else:
            actor = self._corporate_access.actor
            if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
                raise AuthorizationError(
                    "薬歴の起票にはスタッフを特定できるActorが必要です。"
                )
            counselor_id = actor.staff_id
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id, staff_id=counselor_id
            )
            self._counselor_service.ensure_pharmacist(qualifications)
            counseled_at = CounselingTimestamp(self._clock.now())
            imported_at = None

        additions = tuple(
            BillingAddition(
                code=BillingAdditionCode(item.code),
                name=BillingAdditionName(item.name),
                points=item.points,
                quantity=item.quantity,
            )
            for item in (command.billing_additions or ())
        )

        record = MedicationHistoryRecord.start(
            corporate_id=corporate_id,
            store_id=store_id,
            patient_id=dispensing.patient_id,
            dispensing_id=dispensing.id,
            prescription_id=dispensing.prescription_id,
            counselor_id=counselor_id,
            counseled_at=counseled_at,
            method=(
                parse_enum(CounselingMethod, command.method, "服薬指導の方法")
                if command.method is not None
                else None
            ),
            soap=build_soap(command.soap),
            handbook_status=(
                build_handbook_status(command.handbook_status)
                if command.handbook_status is not None
                else None
            ),
            residual_drug=(
                build_residual_drug(command.residual_drug)
                if command.residual_drug is not None
                else None
            ),
            information_sheet_provided=command.information_sheet_provided,
            profile_updates=build_profile_updates(command.profile_updates),
            billing_additions=additions,
            source_system=build_optional(
                command.source_system, MedicationHistorySourceSystem
            ),
            imported_at=imported_at,
        )
        await self._repository.save(record)
        return MedicationHistoryDto.from_entity(record)
