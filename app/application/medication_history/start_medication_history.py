"""服薬指導の記録を下書きとして起こすユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.exceptions import AuthorizationError, NotFoundError
from app.application.common.optional_conversion import build_optional
from app.application.common.unit_of_work import UnitOfWork
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
    ReceptionMedicationHistoryBoundary,
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
from app.domain.medication_history.exceptions import (
    MedicationHistoryDomainError,
    SoapContentRequiredError,
)
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
from app.domain.staff.primitives import StaffId
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
    imported_at: datetime | None = None
    counselor_id: str | None = None
    counseled_at: datetime | None = None
    reception_id: str | None = None


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
        unit_of_work: UnitOfWork,
        reception_source: ReceptionMedicationHistoryBoundary | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._store_reference = store_reference
        self._dispensing_reference = dispensing_reference
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._unit_of_work = unit_of_work
        self._reception_source = reception_source

    async def execute(
        self, command: StartMedicationHistoryCommand
    ) -> MedicationHistoryDto:
        """境界と集約外の不変条件を確認して下書きを保存する。

        **患者・処方箋は調剤セッションから決まる。** Commandで受け取ると、調剤と
        食い違う薬歴を作れてしまう。ここから取る限り調剤との一致は
        **構築の形で保証される**ので、判定を重ねて置かない。

        記載者は信頼済みActorから決める。指導実績は明示入力された場合だけ記録し、
        記載者や保存時刻から推定しない。
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
        source_system = command.source_system
        imported_at_value = command.imported_at
        addition_inputs = command.billing_additions or ()
        if command.reception_id is not None:
            self._unit_of_work.ensure_active()
            if self._reception_source is None:
                raise NotFoundError(
                    "受付由来情報を確認できません。", code="RECEPTION_NOT_FOUND"
                )
            reception_source = await self._reception_source.get_for_initial_save(
                corporate_id=corporate_id,
                store_id=store_id,
                reception_id=command.reception_id,
            )
            if reception_source is None:
                raise NotFoundError(
                    "指定された受付が見つかりません。", code="RECEPTION_NOT_FOUND"
                )
            if (
                reception_source.patient_id != dispensing.patient_id
                or reception_source.dispensing_id != dispensing.id
                or (
                    reception_source.prescription_id is not None
                    and reception_source.prescription_id != dispensing.prescription_id
                )
            ):
                raise MedicationHistoryDomainError(
                    "受付と患者・処方・調剤セッションが一致しません。"
                )
            if reception_source.medication_history_id is not None:
                raise MedicationHistoryDomainError(
                    "受付にはすでに薬歴が関連付いています。"
                )
            if reception_source.is_follow_up:
                raise MedicationHistoryDomainError(
                    "フォローアップ受付から初回薬歴は作成できません。"
                )
            if (
                command.source_system is not None
                or command.imported_at is not None
                or command.billing_additions is not None
            ):
                raise MedicationHistoryDomainError(
                    "受付由来情報は受付記録から取得してください。"
                )
            source_system = reception_source.source_system
            imported_at_value = reception_source.imported_at
            addition_inputs = reception_source.billing_additions
        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
            raise AuthorizationError(
                "薬歴の初回保存にはスタッフを特定できるActorが必要です。"
            )
        recorded_by = actor.staff_id
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id, staff_id=recorded_by
        )
        self._counselor_service.ensure_pharmacist(qualifications)

        if (command.counselor_id is None) != (command.counseled_at is None):
            raise MedicationHistoryDomainError(
                "実際の指導者と指導日時は両方指定するか、両方未指定にしてください。"
            )
        counselor_id = (
            StaffId.parse(command.counselor_id)
            if command.counselor_id is not None
            else None
        )
        counseled_at = (
            CounselingTimestamp(command.counseled_at)
            if command.counseled_at is not None
            else None
        )
        if counselor_id is not None and counselor_id != recorded_by:
            counselor_qualifications = (
                await self._staff_qualification.get_qualifications(
                    corporate_id=corporate_id, staff_id=counselor_id
                )
            )
            self._counselor_service.ensure_pharmacist(counselor_qualifications)

        if source_system == "NSIPS" and imported_at_value is None:
            raise MedicationHistoryDomainError(
                "NSIPS由来の薬歴には受信した取込時刻が必要です。"
            )
        if imported_at_value is not None and source_system != "NSIPS":
            raise MedicationHistoryDomainError(
                "取込時刻を記録する場合は取込元システムを指定してください。"
            )
        imported_at = (
            MedicationHistoryImportTimestamp(imported_at_value)
            if imported_at_value is not None
            else None
        )

        additions = tuple(
            BillingAddition(
                code=BillingAdditionCode(item.code),
                name=BillingAdditionName(item.name),
                points=item.points,
                quantity=item.quantity,
            )
            for item in addition_inputs
        )

        soap = build_soap(command.soap)
        if not soap.has_content:
            raise SoapContentRequiredError()

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
            soap=soap,
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
            source_system=build_optional(source_system, MedicationHistorySourceSystem),
            imported_at=imported_at,
            recorded_by=recorded_by,
        )
        await self._repository.save(record)
        if command.reception_id is not None:
            assert self._reception_source is not None
            await self._reception_source.associate_medication_history(
                corporate_id=corporate_id,
                store_id=store_id,
                reception_id=command.reception_id,
                medication_history_id=record.id,
            )
        return MedicationHistoryDto.from_entity(record)
