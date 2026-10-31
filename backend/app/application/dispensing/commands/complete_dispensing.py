"""Applicationのcomplete_dispensingを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date, business_now
from app.application.common.unit_of_work import UnitOfWork
from app.application.dispensing.commands.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.commands.services.support import (
    load_dispensing_or_raise,
    resolve_acting_staff_id,
)
from app.application.dispensing.interfaces.references import (
    DispensingPolicyBoundary,
    PrescriptionCompletionBoundary,
    StaffPersonBoundary,
    StaffQualificationBoundary,
)
from app.application.dispensing.values import parse_enum
from app.domain.corporate.identifiers import CorporateId
from app.domain.dispensing.exceptions import (
    PrescriptionAuditRequiredConflictError,
    SelfVerificationProhibitedConflictError,
)
from app.domain.dispensing.identifiers import DispensingId
from app.domain.dispensing.primitives import (
    DispensingCompletionTimestamp,
    DispensingCompletionType,
    NextDispensingDate,
)
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.dispensing.services import DispensingPharmacistService


@dataclass(frozen=True, kw_only=True)
class CompleteDispensingCommand:
    """調剤完了の入力データ。"""

    corporate_id: str
    dispensing_id: str
    completion_type: str
    next_dispensing_date: date | None = None


class CompleteDispensingUseCase:
    """患者へ交付して調剤セッションを完了する。

    **処方箋を調剤済へ進める契機は調剤終了区分である**（調剤編
    リフィル処方箋情報レコード(521)）。「調剤回数が総使用回数に達したこと」
    ではない。規格は「達していないが次回以降の調剤が不要となった場合」も終了と
    定めるため、判断は調剤側から渡される。

    調剤セッションの保存と処方箋の状態更新は、片方だけが残ると調剤の記録と
    処方箋の状態が食い違う。**トランザクションの開始・確定を実行スコープが
    担い、ユースケースは必須の UnitOfWork で境界が開始済みであることを確認する。**
    永続化実装はトランザクションの外では読み書きできないため、境界を張り忘れた
    まま2件を書き込む経路は存在しない。
    """

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        prescription_completion: PrescriptionCompletionBoundary,
        unit_of_work: UnitOfWork,
        clock: Clock,
        policy_boundary: DispensingPolicyBoundary | None = None,
        staff_person: StaffPersonBoundary | None = None,
        staff_qualification: StaffQualificationBoundary | None = None,
        pharmacist_service: DispensingPharmacistService | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._prescription_completion = prescription_completion
        self._unit_of_work = unit_of_work
        self._clock = clock
        self._policy_boundary = policy_boundary
        self._staff_person = staff_person
        self._staff_qualification = staff_qualification
        self._pharmacist_service = pharmacist_service

    async def execute(self, command: CompleteDispensingCommand) -> DispensingProcessDto:
        """調剤セッションを完了し、終了区分なら処方箋も調剤済にする。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_DISPENSING
        )
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(command.dispensing_id),
        )
        actor_staff_id = resolve_acting_staff_id(self._corporate_access.actor)
        if self._staff_qualification is not None:
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id,
                staff_id=actor_staff_id,
                store_id=process.store_id,
                as_of=business_date(self._clock),
            )
            (
                self._pharmacist_service or DispensingPharmacistService()
            ).ensure_dispenser(qualifications)

        # 完了前の実効ポリシー再判定
        if self._policy_boundary is not None:
            policy = await self._policy_boundary.get_effective_policy(
                corporate_id=corporate_id, store_id=process.store_id
            )
            if policy.require_prescription_audit and (
                process.audit is None or process.audit.has_issues
            ):
                raise PrescriptionAuditRequiredConflictError()
            if (
                policy.prohibit_self_verification
                and self._staff_person is not None
                and process.verification is not None
            ):
                dispenser_person = await self._staff_person.person_of(
                    corporate_id, process.dispenser_id
                )
                verifier_person = await self._staff_person.person_of(
                    corporate_id, process.verification.verifier_id
                )
                if (
                    dispenser_person is not None
                    and verifier_person is not None
                    and dispenser_person == verifier_person
                ):
                    raise SelfVerificationProhibitedConflictError()

        completion_type = parse_enum(
            DispensingCompletionType, command.completion_type, "調剤終了区分"
        )
        completed_at = business_now(self._clock)
        process = process.complete(
            completion_type=completion_type,
            next_dispensing_date=NextDispensingDate(command.next_dispensing_date)
            if command.next_dispensing_date is not None
            else None,
            completed_at=DispensingCompletionTimestamp(completed_at.astimezone(UTC)),
            completed_on=completed_at.date(),
        )
        await self._repository.save(process)
        if completion_type is DispensingCompletionType.COMPLETED:
            await self._prescription_completion.complete_dispensing(
                corporate_id=corporate_id,
                prescription_id=process.prescription_id,
                dispensed_on=process.dispensed_date.value,
            )
        return DispensingProcessDto.from_entity(process)
