"""外部主体に対応するアカウント・本人・所属の保存値だけを取得する。"""

from app.application.identity.interfaces.resolve_actor_query_reader import (
    ResolveActorQueryReader,
)
from app.application.identity.queries.dtos.identity_resolution import (
    IdentityResolutionSnapshot,
    ManagerIdentitySnapshot,
    MembershipIdentitySnapshot,
    StaffAffiliationIdentitySnapshot,
    StoreIdentitySnapshot,
)
from app.domain.identity.primitives import AccountStatus, ExternalSubjectKey
from app.domain.identity.repositories import (
    AccountPersonRepository,
    CorporateMembershipRepository,
    UserAccountRepository,
    VendorOperatorRepository,
)
from app.domain.staff.repositories import StaffRepository
from app.domain.store.primitives import StoreStatus
from app.domain.store.repositories import (
    StoreManagerAssignmentRepository,
    StoreRepository,
)


class ResolveActorProjection(ResolveActorQueryReader):
    """利用状態やロールを判断せず、Applicationへ参照事実を渡す。"""

    def __init__(
        self,
        people: AccountPersonRepository,
        accounts: UserAccountRepository,
        memberships: CorporateMembershipRepository,
        managers: StoreManagerAssignmentRepository,
        vendor_operators: VendorOperatorRepository | None = None,
        staffs: StaffRepository | None = None,
        stores: StoreRepository | None = None,
    ) -> None:
        self._people = people
        self._accounts = accounts
        self._memberships = memberships
        self._managers = managers
        self._vendor_operators = vendor_operators
        self._staffs = staffs
        self._stores = stores

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> IdentityResolutionSnapshot | None:
        """主体からアカウントを引き、欠落を含む関連情報を不変の投影で返す。"""
        if self._vendor_operators is not None:
            operator = await self._vendor_operators.get_by_subject(subject)
            if operator is not None:
                return IdentityResolutionSnapshot(
                    operator_id=operator.id,
                    external_subject=subject,
                    account_status=AccountStatus.ACTIVE
                    if operator.is_active
                    else AccountStatus.SUSPENDED,
                    is_vendor_admin=True,
                )
            if subject.value.startswith("vendor:"):
                return None
        account = await self._accounts.get_by_subject(subject)
        if account is None:
            return None
        person = await self._people.get(account.person_id)
        membership = await self._memberships.find_active_for_account(account.id)
        assignments = (
            await self._managers.list_by_staff(
                membership.corporate_id, membership.staff_id
            )
            if membership is not None and membership.staff_id is not None
            else []
        )
        staff_is_active: bool | None = None
        staff_affiliations: tuple[StaffAffiliationIdentitySnapshot, ...] = ()
        loaded_stores: list[StoreIdentitySnapshot] = []
        if membership is not None and self._staffs is not None:
            if membership.staff_id is not None:
                staff = await self._staffs.get(
                    corporate_id=membership.corporate_id,
                    staff_id=membership.staff_id,
                )
                if staff is not None and staff.corporate_id == membership.corporate_id:
                    staff_is_active = staff.is_active
                    staff_affiliations = tuple(
                        StaffAffiliationIdentitySnapshot(
                            store_id=aff.store_id,
                            starts_on=aff.period.start_date,
                            ends_on=aff.period.end_date,
                        )
                        for aff in staff.affiliations
                    )
                else:
                    staff_is_active = False
            else:
                staff_is_active = False
        if membership is not None and self._stores is not None:
            for store_id in sorted(membership.store_ids, key=lambda item: item.value):
                store = await self._stores.get(store_id)
                if store is not None:
                    loaded_stores.append(
                        StoreIdentitySnapshot(
                            id=store.id,
                            corporate_id=store.corporate_id,
                            name=store.names.name.value,
                            code=store.code.value if store.code is not None else None,
                            is_active=store.status == StoreStatus.ACTIVE,
                        )
                    )
        membership_snapshot = (
            MembershipIdentitySnapshot(
                id=membership.id,
                account_id=membership.account_id,
                corporate_id=membership.corporate_id,
                status=membership.status,
                role=membership.role,
                staff_id=membership.staff_id,
                store_ids=membership.store_ids,
                suspended_store_ids=membership.suspended_store_ids,
                manager_assignments=tuple(
                    ManagerIdentitySnapshot(
                        corporate_id=item.corporate_id,
                        store_id=item.store_id,
                        staff_id=item.staff_id,
                        person_id=item.person_id,
                        status=item.status,
                        starts_on=item.period.starts_on,
                        ends_on=item.period.ends_on,
                    )
                    for item in assignments
                ),
                staff_is_active=staff_is_active,
                staff_affiliations=staff_affiliations,
                stores=tuple(loaded_stores),
            )
            if membership is not None
            else None
        )
        return IdentityResolutionSnapshot(
            account_id=account.id,
            account_person_id=account.person_id,
            person_id=person.id if person is not None else None,
            external_subject=account.external_subject,
            account_status=account.status,
            is_vendor_admin=account.is_vendor_admin,
            membership=membership_snapshot,
        )
