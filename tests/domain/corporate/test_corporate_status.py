from app.domain.corporate import CorporateStatus
from tests.application.corporate.helpers import create_corporate


def test_corporate_status_transitions() -> None:
    corporate = create_corporate()

    inactive = corporate.deactivate()
    assert inactive.status is CorporateStatus.INACTIVE
    assert inactive.is_active is False

    active = inactive.activate()
    assert active.status is CorporateStatus.ACTIVE
    assert active.is_active is True
