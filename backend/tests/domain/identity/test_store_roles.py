"""店舗ごとに独立した操作権限。"""

from app.domain.corporate.identifiers import CorporateId
from app.domain.identity.entities import CorporateMembership
from app.domain.identity.identifiers import CorporateMembershipId
from app.domain.identity.primitives import MembershipRole, StoreRole
from app.domain.identity.value_objects import StoreRoleAssignment
from app.domain.shared.actor import UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId


def test_店舗権限_店舗ごとに異なるロールの場合_独立して変更できる() -> None:
    # Arrange
    a, b = StoreId.generate(), StoreId.generate()
    membership = CorporateMembership(
        id=CorporateMembershipId.generate(),
        account_id=UserAccountId.generate(),
        corporate_id=CorporateId.generate(),
        role=MembershipRole.MEMBER,
        staff_id=StaffId.generate(),
        store_roles=(
            StoreRoleAssignment(store_id=a, role=StoreRole.EDITOR),
            StoreRoleAssignment(store_id=b, role=StoreRole.VIEWER),
        ),
    )
    # Act
    changed = membership.change_store_role(store_id=a, role=StoreRole.VIEWER)
    # Assert
    assert membership.role_for_store(a) is StoreRole.EDITOR
    assert changed.role_for_store(a) is StoreRole.VIEWER
    assert changed.role_for_store(b) is StoreRole.VIEWER
