"""Applicationのverify_dispensingを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary_models import Permission
from app.application.access_control.interfaces.corporate_access import (
    CorporateAccessBoundary,
)
from app.application.common.clock import Clock, business_date
from app.application.common.optional_conversion import build_optional
from app.application.dispensing.commands.dtos.get_dispensing import DispensingProcessDto
from app.application.dispensing.commands.services.support import (
    load_dispensing_or_raise,
    resolve_acting_staff_id,
)
from app.application.dispensing.interfaces.references import (
    DispensingPolicyBoundary,
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
    VerificationNotes,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.dispensing.repositories import DispensingProcessRepository
from app.domain.dispensing.services import DispensingPharmacistService


@dataclass(frozen=True, kw_only=True)
class VerifyDispensingCommand:
    """最終鑑査記録の入力データ。鑑査日時は含めない。"""

    corporate_id: str
    dispensing_id: str
    result: str
    verifier_id: str | None = None
    notes: str | None = None


class VerifyDispensingUseCase:
    """鑑査者の資格を確認して最終鑑査の結果を記録する。"""

    def __init__(
        self,
        repository: DispensingProcessRepository,
        corporate_access: CorporateAccessBoundary,
        staff_qualification: StaffQualificationBoundary,
        pharmacist_service: DispensingPharmacistService,
        clock: Clock,
        policy_boundary: DispensingPolicyBoundary | None = None,
        staff_person: StaffPersonBoundary | None = None,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access
        self._staff_qualification = staff_qualification
        self._pharmacist_service = pharmacist_service
        self._clock = clock
        self._policy_boundary = policy_boundary
        self._staff_person = staff_person

    async def execute(self, command: VerifyDispensingCommand) -> DispensingProcessDto:
        """薬剤師資格を確認し、注入Clock由来の日時で鑑査結果を記録する。

        調剤者本人が鑑査できないこと（一括代行署名の禁止）は集約が判定する。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id, permission=Permission.MANAGE_DISPENSING
        )
        process = await load_dispensing_or_raise(
            self._repository,
            corporate_id=corporate_id,
            dispensing_id=DispensingId.parse(command.dispensing_id),
        )
        verifier_id = resolve_acting_staff_id(
            self._corporate_access.actor, command.verifier_id
        )
        qualifications = await self._staff_qualification.get_qualifications(
            corporate_id=corporate_id,
            staff_id=verifier_id,
            store_id=process.store_id,
            as_of=business_date(self._clock),
        )
        self._pharmacist_service.ensure_verifier(qualifications)

        result = parse_enum(VerificationResult, command.result, "鑑査結果")

        # ポリシー検証
        if self._policy_boundary is not None:
            policy = await self._policy_boundary.get_effective_policy(
                corporate_id=corporate_id, store_id=process.store_id
            )
            if (
                policy.require_prescription_audit
                and result.is_passed
                and (process.audit is None or process.audit.has_issues)
            ):
                raise PrescriptionAuditRequiredConflictError()
            if policy.prohibit_self_verification and self._staff_person is not None:
                dispenser_person = await self._staff_person.person_of(
                    corporate_id, process.dispenser_id
                )
                verifier_person = await self._staff_person.person_of(
                    corporate_id, verifier_id
                )
                if (
                    dispenser_person is not None
                    and verifier_person is not None
                    and dispenser_person == verifier_person
                ):
                    raise SelfVerificationProhibitedConflictError()

        process = process.verify(
            verifier_id=verifier_id,
            verified_at=VerificationTimestamp(self._clock.now()),
            result=result,
            notes=build_optional(command.notes, VerificationNotes),
        )
        await self._repository.save(process)
        return DispensingProcessDto.from_entity(process)
