"""Applicationのclinical_store_guardを定義する。"""

from __future__ import annotations

from app.application.access_control.boundary_models import (
    ActorRole,
    Permission,
    ResolvedActorContext,
)
from app.application.access_control.interfaces.store_operations import (
    StoreOperation,
    StoreOperationBoundary,
)
from app.application.access_control.policies import AuthorizationService
from app.application.common.clock import Clock, business_date
from app.application.common.exceptions import AuthorizationError
from app.application.common.optional_conversion import unwrap
from app.application.common.organization_lock import OrganizationLock
from app.application.prescription.interfaces.references import (
    MedicineRestrictionBoundary,
)
from app.domain.care_event.entities import Event
from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.entities import CoverageSelectionRecord
from app.domain.dispensing.entities import DispensingProcess
from app.domain.dispensing.exceptions import DispensingPharmacistQualificationError
from app.domain.dispensing.primitives import DispensingProcessStatus
from app.domain.identity.primitives import AccountStatus
from app.domain.identity.repositories import (
    CorporateMembershipRepository,
    UserAccountRepository,
)
from app.domain.medication_history.entities import MedicationHistoryRecord
from app.domain.medication_history.exceptions import CounselorQualificationError
from app.domain.prescription.entities import Prescription
from app.domain.prescription.exceptions import (
    InquiryPharmacistQualificationError,
    MedicineClassificationMissingError,
    MedicineClassificationUnknownError,
)
from app.domain.prescription.primitives import (
    MedicineCode,
    MedicineCodeType,
    MedicineRestrictionFlag,
    PrescriptionStatus,
)
from app.domain.prescription.value_objects import MedicineIdentifier
from app.domain.staff.repositories import StaffRepository
from app.domain.staff.value_objects import PharmacistProfile
from app.domain.store.identifiers import StoreId


def _to_prescription_identifier(
    code_type_val: str, code_val: str | None
) -> MedicineIdentifier:
    return MedicineIdentifier(
        code_type=MedicineCodeType(code_type_val),
        code=MedicineCode(code_val) if code_val is not None else None,
    )


class ClinicalStoreWriteGuard:
    """保存する集約が持つ店舗で権限と現在状態を検証する。"""

    def __init__(
        self,
        stores: StoreOperationBoundary,
        authorization: AuthorizationService,
        lock: OrganizationLock,
        *,
        medicine_restriction: MedicineRestrictionBoundary | None = None,
        clock: Clock | None = None,
        accounts: UserAccountRepository | None = None,
        memberships: CorporateMembershipRepository | None = None,
        staffs: StaffRepository | None = None,
    ) -> None:
        self._stores = stores
        self._authorization = authorization
        self._lock = lock
        self._medicine_restriction = medicine_restriction
        self._clock = clock
        self._accounts = accounts
        self._memberships = memberships
        self._staffs = staffs

    async def _reverify_actor(
        self,
        *,
        corporate_id: CorporateId,
        store_id: StoreId,
        aggregate: object,
        is_new: bool,
    ) -> None:
        """法人ロック取得後にActorのアカウント・所属・スタッフ資格を再確認する。"""
        actor = self._authorization.actor
        if (
            not isinstance(actor, ResolvedActorContext)
            or ActorRole.VENDOR_SYSTEM_ADMIN in actor.roles
        ):
            return
        if self._accounts is not None and actor.account_id is not None:
            account = await self._accounts.get(actor.account_id)
            if account is None or account.status is not AccountStatus.ACTIVE:
                raise AuthorizationError(
                    "アカウントが停止されているため業務を実行できません。"
                )
        if self._memberships is not None and actor.membership_id is not None:
            membership = await self._memberships.get(actor.membership_id)
            if membership is None or membership.status is not AccountStatus.ACTIVE:
                raise AuthorizationError(
                    "法人アクセス権が停止されているため業務を実行できません。"
                )
            if (
                ActorRole.CORPORATE_ADMIN not in actor.roles
                and store_id not in membership.active_store_ids
            ):
                raise AuthorizationError("指定された店舗への利用権限がありません。")
        if self._staffs is not None and actor.staff_id is not None:
            staff = await self._staffs.get(
                corporate_id=corporate_id, staff_id=actor.staff_id
            )
            if staff is None or not staff.is_active:
                raise AuthorizationError(
                    "スタッフが退職または停止されているため業務を実行できません。"
                )
            if self._clock is not None:
                today = business_date(self._clock)
                if staff.current_home_store_id(
                    today
                ) != store_id and store_id not in staff.current_concurrent_store_ids(
                    today
                ):
                    raise AuthorizationError(
                        "指定された店舗に当日有効な所属がありません。"
                    )
            has_pharmacist = staff.qualifications.has(PharmacistProfile)
            if (
                isinstance(aggregate, DispensingProcess)
                and aggregate.status is not DispensingProcessStatus.CANCELLED
                and not has_pharmacist
            ):
                raise DispensingPharmacistQualificationError()
            if (
                isinstance(aggregate, Prescription)
                and not is_new
                and aggregate.inquiries
                and aggregate.status is PrescriptionStatus.RECEIVED
                and not has_pharmacist
            ):
                raise InquiryPharmacistQualificationError()
            if isinstance(aggregate, MedicationHistoryRecord) and not has_pharmacist:
                requires_pharmacist = (
                    is_new and aggregate.recorded_by == actor.staff_id
                ) or (
                    not is_new
                    and (
                        aggregate.finalized_by == actor.staff_id
                        or (
                            bool(aggregate.amendments)
                            and aggregate.amendments[-1].amended_by == actor.staff_id
                        )
                        or (
                            bool(aggregate.fact_corrections)
                            and aggregate.fact_corrections[-1].corrected_by
                            == actor.staff_id
                        )
                        or any(
                            c.acknowledged_by == actor.staff_id
                            or (
                                bool(c.review_events)
                                and c.review_events[-1].reviewed_by == actor.staff_id
                            )
                            for c in aggregate.external_corrections
                        )
                        or (
                            bool(aggregate.tracing_reports)
                            and aggregate.tracing_reports[-1].reporter_id
                            == actor.staff_id
                            and aggregate.tracing_reports[-1].response is None
                        )
                    )
                )
                if requires_pharmacist:
                    raise CounselorQualificationError()

    async def check(self, aggregate: object, is_new: bool) -> None:
        """HTTPの店舗指定ではなく保存対象の店舗へ検証を適用する。"""
        has_narcotics = False
        if isinstance(aggregate, Prescription):
            if aggregate.status is PrescriptionStatus.CANCELLED:
                await self._lock.acquire(f"corporate:{aggregate.corporate_id.value}")
                self._authorization.require_store(
                    permission=Permission.MANAGE_PRESCRIPTION,
                    target_corporate_id=aggregate.corporate_id,
                    target_store_id=aggregate.store_id,
                )
                await self._reverify_actor(
                    corporate_id=aggregate.corporate_id,
                    store_id=aggregate.store_id,
                    aggregate=aggregate,
                    is_new=is_new,
                )
                return
            permission = Permission.MANAGE_PRESCRIPTION
            operation = (
                StoreOperation.REGISTER_PRESCRIPTION
                if is_new
                else StoreOperation.RECORD_DISPENSING
            )
            if self._medicine_restriction is not None and self._clock is not None:
                today = business_date(self._clock)
                classifications = await self._medicine_restriction.classify(
                    identifiers=aggregate.medicine_identifiers,
                    as_of=today,
                )
                has_narcotics = any(
                    c.is_narcotic is MedicineRestrictionFlag.YES
                    for c in classifications.values()
                )
        elif isinstance(aggregate, DispensingProcess):
            if aggregate.status is DispensingProcessStatus.CANCELLED:
                await self._lock.acquire(f"corporate:{aggregate.corporate_id.value}")
                self._authorization.require_store(
                    permission=Permission.MANAGE_DISPENSING,
                    target_corporate_id=aggregate.corporate_id,
                    target_store_id=aggregate.store_id,
                )
                await self._reverify_actor(
                    corporate_id=aggregate.corporate_id,
                    store_id=aggregate.store_id,
                    aggregate=aggregate,
                    is_new=is_new,
                )
                return
            permission = Permission.MANAGE_DISPENSING
            operation = (
                StoreOperation.START_DISPENSING
                if is_new
                else StoreOperation.RECORD_DISPENSING
            )
            if self._medicine_restriction is not None and self._clock is not None:
                today = business_date(self._clock)
                dispensed_ids = tuple(
                    _to_prescription_identifier(
                        m.identifier.code_type.value,
                        unwrap(m.identifier.code),
                    )
                    for rp in aggregate.dispensed_rps
                    for m in rp.medicines
                )
                classifications = await self._medicine_restriction.classify(
                    identifiers=dispensed_ids,
                    as_of=today,
                )
                for identifier in dispensed_ids:
                    classification = classifications.get(identifier)
                    if classification is None:
                        raise MedicineClassificationMissingError()
                    if classification.is_narcotic.is_unknown:
                        raise MedicineClassificationUnknownError()
                has_narcotics = any(
                    c.is_narcotic is MedicineRestrictionFlag.YES
                    for c in classifications.values()
                )
        elif isinstance(aggregate, Event):
            permission = Permission.MANAGE_EVENT
            operation = StoreOperation.CREATE_EVENT
        elif isinstance(aggregate, CoverageSelectionRecord):
            permission = Permission.MANAGE_RECEPTION
            operation = StoreOperation.RECORD_RECEPTION
        elif isinstance(aggregate, MedicationHistoryRecord):
            permission = Permission.MANAGE_MEDICATION_HISTORY
            operation = (
                StoreOperation.START_HISTORY if is_new else StoreOperation.AMEND_HISTORY
            )
        else:
            return
        await self._lock.acquire(f"corporate:{aggregate.corporate_id.value}")
        self._authorization.require_store(
            permission=permission,
            target_corporate_id=aggregate.corporate_id,
            target_store_id=aggregate.store_id,
        )
        await self._reverify_actor(
            corporate_id=aggregate.corporate_id,
            store_id=aggregate.store_id,
            aggregate=aggregate,
            is_new=is_new,
        )
        await self._stores.require_allowed(
            corporate_id=aggregate.corporate_id,
            store_id=aggregate.store_id,
            operation=operation,
            has_narcotics=has_narcotics,
        )
