"""調剤セッション（調剤録）の法定保存満了日導出テスト。"""

from datetime import UTC, date, datetime

from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import (
    DispensingCompletionTimestamp,
    DispensingCompletionType,
)
from app.domain.shared.preservation import (
    PreservationPolicy,
    PreservationPolicyCatalog,
    PreservationRecordKind,
    RetentionYears,
)
from tests.factories.dispensing_factory import create_dispensing, verify_passed


def _completed_dispensing(dispensed_on: date) -> DispensingProcess:
    completed_at = datetime(
        dispensed_on.year,
        dispensed_on.month,
        dispensed_on.day,
        tzinfo=UTC,
    )
    return verify_passed(create_dispensing(dispensed_on=dispensed_on)).complete(
        completion_type=DispensingCompletionType.COMPLETED,
        completed_at=DispensingCompletionTimestamp(completed_at),
        completed_on=dispensed_on,
    )


def test_dispensing_retention_expiry() -> None:
    """TC-17: 調剤録の法定保存満了日が調剤日とポリシーカタログに基づいて算出される。"""
    # 2026-03-15 調剤（法改正前）
    dispensing_old = _completed_dispensing(date(2026, 3, 15))
    # 2026-04-10 調剤（薬剤師法改正の施行前）
    dispensing_new = _completed_dispensing(date(2026, 4, 10))

    catalog = PreservationPolicyCatalog.create_standard_statutory_catalog(
        PreservationRecordKind.DISPENSING_RECORD
    )

    # 改正前（3年）: 2026-03-15 -> 2029-03-15
    assert dispensing_old.calculate_retention_expiry_date(catalog) == date(2029, 3, 15)
    # 施行前（3年）: 2026-04-10 -> 2029-04-10
    assert dispensing_new.calculate_retention_expiry_date(catalog) == date(2029, 4, 10)


def test_dispensing_retention_expiry_multiple_obligations() -> None:
    """TC-40-12: 調剤録集約において複数義務のうち遅い満了日を採用する。"""
    dispensing_revised = _completed_dispensing(date(2027, 5, 20))
    statutory_catalog = PreservationPolicyCatalog.create_standard_statutory_catalog(
        PreservationRecordKind.DISPENSING_RECORD
    )
    insured_rule_catalog = PreservationPolicyCatalog(
        record_kind=PreservationRecordKind.DISPENSING_RECORD,
        policies=(
            PreservationPolicy(
                name="療担規則の現行3年保存",
                retention_years=RetentionYears(3),
                effective_from=date.min,
            ),
        ),
    )
    # 2027-05-20: 薬剤師法改正後5年（2032-05-20）と療担規則3年（2030-05-20）で遅い5年を採用
    assert dispensing_revised.calculate_retention_expiry_date(
        statutory_catalog,
        insured_rule_catalog,
    ) == date(2032, 5, 20)

    # 完了日と異なる起算日の義務（完結日: 2027-05-25）との比較
    dispensing_pre = _completed_dispensing(date(2027, 5, 19))
    assert dispensing_pre.calculate_retention_expiry_date(
        statutory_catalog,
        (insured_rule_catalog, date(2027, 5, 25)),
    ) == date(2030, 5, 25)
