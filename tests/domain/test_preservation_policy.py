"""調剤録・薬歴の法定保存年数・時点付き履歴管理ポリシーのテスト。"""

from datetime import date

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.preservation import (
    OverlappingPreservationPolicyError,
    PreservationPolicy,
    PreservationPolicyCatalog,
    PreservationPolicyNotFoundError,
    PreservationPolicyPeriodInvertedError,
    RetentionYears,
)


def test_retention_years_valid() -> None:
    """TC-01: 正の整数でRetentionYearsが正常に生成できる。"""
    ry3 = RetentionYears(3)
    ry5 = RetentionYears(5)
    assert ry3.value == 3
    assert ry5.value == 5


@pytest.mark.parametrize("invalid_val", [0, -1, -5])
def test_retention_years_non_positive_rejected(invalid_val: int) -> None:
    """TC-02: 0以下の値でRetentionYearsを生成しようとすると拒否される。"""
    with pytest.raises(DomainValidationError):
        RetentionYears(invalid_val)


@pytest.mark.parametrize("invalid_type", ["3", True, 3.5])
def test_retention_years_invalid_type_rejected(invalid_type: object) -> None:
    """TC-03: 整数以外の型でRetentionYearsを生成しようとすると拒否される。"""
    with pytest.raises(DomainValidationError):
        RetentionYears(invalid_type)  # type: ignore[arg-type]


def test_preservation_policy_is_effective_at() -> None:
    """TC-04: 指定日付がポリシー有効期間内かを正しく判定できる。"""
    policy = PreservationPolicy(
        name="改正前3年保存",
        retention_years=RetentionYears(3),
        effective_from=date(2020, 4, 1),
        effective_to=date(2026, 3, 31),
    )
    assert policy.is_effective_at(date(2020, 4, 1)) is True
    assert policy.is_effective_at(date(2023, 5, 15)) is True
    assert policy.is_effective_at(date(2026, 3, 31)) is True
    # 範囲外
    assert policy.is_effective_at(date(2020, 3, 31)) is False
    assert policy.is_effective_at(date(2026, 4, 1)) is False


def test_preservation_policy_open_ended() -> None:
    """TC-05: effective_to=Noneの無期限ポリシーは開始日以降すべてで有効。"""
    policy = PreservationPolicy(
        name="改正後5年保存",
        retention_years=RetentionYears(5),
        effective_from=date(2026, 4, 1),
        effective_to=None,
    )
    assert policy.is_effective_at(date(2026, 3, 31)) is False
    assert policy.is_effective_at(date(2026, 4, 1)) is True
    assert policy.is_effective_at(date(2035, 12, 31)) is True


def test_preservation_policy_inverted_period_rejected() -> None:
    """TC-06: 開始日が終了日より後のポリシーは作成できない。"""
    with pytest.raises((PreservationPolicyPeriodInvertedError, DomainValidationError)):
        PreservationPolicy(
            name="不正期間ポリシー",
            retention_years=RetentionYears(3),
            effective_from=date(2026, 4, 1),
            effective_to=date(2026, 3, 31),
        )


def test_calculate_expiry_date_standard() -> None:
    """TC-07: 民法第140条（初日不算入）・第143条（暦日計算）に基づく満了日計算。"""
    policy3 = PreservationPolicy(
        name="3年ポリシー",
        retention_years=RetentionYears(3),
        effective_from=date(2020, 1, 1),
    )
    policy5 = PreservationPolicy(
        name="5年ポリシー",
        retention_years=RetentionYears(5),
        effective_from=date(2026, 1, 1),
    )
    # 2023-05-15 起算 -> 3年保存は 2026-05-15 満了
    assert policy3.calculate_expiry_date(date(2023, 5, 15)) == date(2026, 5, 15)
    # 2026-04-01 起算 -> 5年保存は 2031-04-01 満了
    assert policy5.calculate_expiry_date(date(2026, 4, 1)) == date(2031, 4, 1)


def test_calculate_expiry_date_leap_year() -> None:
    """TC-08: うるう年2/29起算の満了日計算（平年の場合は2/28満了）。"""
    policy3 = PreservationPolicy(
        name="3年ポリシー",
        retention_years=RetentionYears(3),
        effective_from=date(2020, 1, 1),
    )
    policy4 = PreservationPolicy(
        name="4年ポリシー",
        retention_years=RetentionYears(4),
        effective_from=date(2020, 1, 1),
    )
    # 2024-02-29 起算 -> 3年後（2027年平年）は 2027-02-28 満了
    assert policy3.calculate_expiry_date(date(2024, 2, 29)) == date(2027, 2, 28)
    # 2024-02-29 起算 -> 4年後（2028年うるう年）は 2028-02-29 満了
    assert policy4.calculate_expiry_date(date(2024, 2, 29)) == date(2028, 2, 29)


def test_policy_catalog_resolution() -> None:
    """TC-09: カタログから基準日に応じたポリシーが解決される。"""
    policy_old = PreservationPolicy(
        name="現行3年",
        retention_years=RetentionYears(3),
        effective_from=date(2020, 4, 1),
        effective_to=date(2026, 3, 31),
    )
    policy_new = PreservationPolicy(
        name="改正5年",
        retention_years=RetentionYears(5),
        effective_from=date(2026, 4, 1),
        effective_to=None,
    )
    catalog = PreservationPolicyCatalog(policies=(policy_old, policy_new))

    resolved_old = catalog.get_policy_for(date(2025, 10, 1))
    assert resolved_old.name == "現行3年"
    assert resolved_old.retention_years.value == 3

    resolved_new = catalog.get_policy_for(date(2026, 4, 1))
    assert resolved_new.name == "改正5年"
    assert resolved_new.retention_years.value == 5


def test_policy_catalog_legal_revision_boundary() -> None:
    """TC-10: 法改正前日（3年）と施行当日（5年）の境界計算。"""
    catalog = PreservationPolicyCatalog.create_standard_statutory_catalog()

    # 2026-03-31 調剤 -> 3年保存 -> 2029-03-31 満了
    assert catalog.calculate_expiry_date(date(2026, 3, 31)) == date(2029, 3, 31)
    # 2026-04-01 調剤 -> 5年保存 -> 2031-04-01 満了
    assert catalog.calculate_expiry_date(date(2026, 4, 1)) == date(2031, 4, 1)


def test_policy_catalog_overlapping_rejected() -> None:
    """TC-11: 期間が重複するポリシーを持つカタログは拒否される。"""
    policy1 = PreservationPolicy(
        name="ポリシー1",
        retention_years=RetentionYears(3),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )
    policy2 = PreservationPolicy(
        name="ポリシー2",
        retention_years=RetentionYears(5),
        effective_from=date(2026, 6, 1),
        effective_to=date(2027, 5, 31),
    )
    with pytest.raises(OverlappingPreservationPolicyError):
        PreservationPolicyCatalog(policies=(policy1, policy2))


def test_policy_catalog_out_of_range_rejected() -> None:
    """TC-12: 定義期間外の日付を指定した場合はポリシー未定義エラー。"""
    policy = PreservationPolicy(
        name="特定期間ポリシー",
        retention_years=RetentionYears(3),
        effective_from=date(2026, 4, 1),
        effective_to=date(2030, 3, 31),
    )
    catalog = PreservationPolicyCatalog(policies=(policy,))

    with pytest.raises(PreservationPolicyNotFoundError):
        catalog.get_policy_for(date(2026, 3, 31))
