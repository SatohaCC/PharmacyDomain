"""調剤録および薬歴の法定保存期間・時点付き履歴管理ポリシー。

薬剤師法第28条（調剤録保存義務）、療担規則第9条（処方箋等の保存義務）、
および将来の5年保存への法改正に対応する、時点付き保存期間ポリシーと満了日計算。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Self

from app.domain.foundation.exceptions import DomainError
from app.domain.foundation.primitives.primitives import BasePositiveInt
from app.domain.foundation.value_object import ValueObject


class PreservationPolicyPeriodInvertedError(DomainError):
    """保存期間ポリシーの開始日が終了日より後である。"""

    default_message = "保存期間ポリシーの開始日は終了日以前である必要があります。"
    default_code = "PRESERVATION_POLICY_PERIOD_INVERTED"


class OverlappingPreservationPolicyError(DomainError):
    """保存期間ポリシーの適用期間が重複している。"""

    default_message = "保存期間ポリシーの適用期間が重複しています。"
    default_code = "OVERLAPPING_PRESERVATION_POLICY"


class PreservationPolicyNotFoundError(DomainError):
    """指定された日付に適用可能な保存期間ポリシーが存在しない。"""

    default_message = "指定された日付に有効な保存期間ポリシーが存在しません。"
    default_code = "PRESERVATION_POLICY_NOT_FOUND"


class RetentionYears(BasePositiveInt):
    """法定保存年数を表すドメインプリミティブ（1以上の正の整数）。"""


@dataclass(frozen=True, kw_only=True)
class PreservationPolicy(ValueObject):
    """法定保存期間ポリシー（有効期間と保存年数）。"""

    name: str
    retention_years: RetentionYears
    effective_from: date
    effective_to: date | None = None

    def validate(self) -> None:
        """ポリシーの不変条件を検証する。"""
        if self.effective_to is not None and self.effective_from > self.effective_to:
            raise PreservationPolicyPeriodInvertedError()

    def is_effective_at(self, target_date: date) -> bool:
        """指定された日付がポリシーの適用範囲内かを判定する。"""
        if target_date < self.effective_from:
            return False
        if self.effective_to is None:
            return True
        return target_date <= self.effective_to

    def calculate_expiry_date(self, base_date: date) -> date:
        """民法第140条（初日不算入）・第143条（暦日計算）に基づく保存満了日を計算する。

        起算日（base_date）の翌日に起算し、指定年数後の応当日の前日を満了日とする。
        暦の上で起算日と同一の月日（base_dateと同日）が満了日となり、
        うるう年2月29日起算で満了年が平年の場合は2月28日を満了日とする。
        """
        target_year = base_date.year + self.retention_years.value
        try:
            return base_date.replace(year=target_year)
        except ValueError:
            # 2月29日かつ満了年が平年の場合は2月28日を満了とする
            return date(target_year, 2, 28)


@dataclass(frozen=True, kw_only=True)
class PreservationPolicyCatalog(ValueObject):
    """保存期間ポリシーのカタログ（履歴管理）。"""

    policies: tuple[PreservationPolicy, ...] = ()

    def validate(self) -> None:
        """ポリシー群の期間重複がないことを検証する。"""
        if not self.policies:
            return
        sorted_policies = sorted(self.policies, key=lambda p: p.effective_from)
        for i in range(len(sorted_policies) - 1):
            p1 = sorted_policies[i]
            p2 = sorted_policies[i + 1]
            if p1.effective_to is None or p1.effective_to >= p2.effective_from:
                raise OverlappingPreservationPolicyError()

    def get_policy_for(self, as_of: date) -> PreservationPolicy:
        """基準日時点に有効な保存期間ポリシーを取得する。"""
        for policy in self.policies:
            if policy.is_effective_at(as_of):
                return policy
        raise PreservationPolicyNotFoundError(
            f"基準日 {as_of.isoformat()} に有効な保存期間ポリシーが存在しません。"
        )

    def calculate_expiry_date(self, base_date: date) -> date:
        """基準日時点で有効なポリシーを解決し、保存満了日を計算する。"""
        policy = self.get_policy_for(base_date)
        return policy.calculate_expiry_date(base_date)

    @classmethod
    def create_standard_statutory_catalog(cls) -> Self:
        """日本の調剤法規（現行3年・法改正後5年）の標準ポリシーカタログを生成する。"""
        old_policy = PreservationPolicy(
            name="薬剤師法第28条・療担規則第9条（現行3年保存）",
            retention_years=RetentionYears(3),
            effective_from=date(2000, 1, 1),
            effective_to=date(2026, 3, 31),
        )
        new_policy = PreservationPolicy(
            name="改正後保存期間（5年保存）",
            retention_years=RetentionYears(5),
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )
        return cls(policies=(old_policy, new_policy))
