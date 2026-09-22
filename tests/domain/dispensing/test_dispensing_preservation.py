"""調剤セッション（調剤録）の法定保存満了日導出テスト。"""

from datetime import date

from app.domain.shared.preservation import PreservationPolicyCatalog
from tests.factories.dispensing_factory import create_dispensing


def test_dispensing_retention_expiry() -> None:
    """TC-17: 調剤録の法定保存満了日が調剤日とポリシーカタログに基づいて算出される。"""
    # 2026-03-15 調剤（法改正前）
    dispensing_old = create_dispensing(dispensed_on=date(2026, 3, 15))
    # 2026-04-10 調剤（法改正後）
    dispensing_new = create_dispensing(dispensed_on=date(2026, 4, 10))

    catalog = PreservationPolicyCatalog.create_standard_statutory_catalog()

    # 改正前（3年）: 2026-03-15 -> 2029-03-15
    assert dispensing_old.calculate_retention_expiry_date(catalog) == date(2029, 3, 15)
    # 改正後（5年）: 2026-04-10 -> 2031-04-10
    assert dispensing_new.calculate_retention_expiry_date(catalog) == date(2031, 4, 10)
