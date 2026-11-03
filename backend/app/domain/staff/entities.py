"""staffのエンティティと集約。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.person_name import PersonNames
from app.domain.staff.exceptions import (
    AffiliationDateConflictError,
    ConcurrentStoreConflictError,
    PrimaryAffiliationDuplicationError,
)
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import (
    EmploymentType,
    JobTitle,
    LeaveReason,
    StaffCode,
    StaffEmailAddress,
    StaffPhoneNumber,
    StaffStatus,
    StoreDuty,
    WeeklyContractHours,
)
from app.domain.staff.value_objects import (
    BaseQualificationProfile,
    DietitianProfile,
    PharmacistProfile,
    RegisteredSellerProfile,
    StaffQualifications,
    StoreAffiliation,
    StoreWorkCondition,
)
from app.domain.store.identifiers import StoreId


def _has_overlapping_period(affiliations: Sequence[StoreAffiliation]) -> bool:
    """開始日昇順に並べ、隣接する2件だけを比較して期間の重なりを検出する。

    ソート後に重なる組 ``(i, j)``（``i < j``）が存在するなら、
    ``start_i <= start_{i+1} <= start_j <= end_i`` が成り立つので
    ``(i, i+1)`` も必ず重なる。よって隣接比較だけで重なりの有無を漏れなく判定できる。
    """
    ordered = sorted(affiliations, key=lambda item: item.period.start_date)
    return any(left.period.overlaps(right.period) for left, right in pairwise(ordered))


@dataclass(frozen=True, eq=False, kw_only=True)
class Staff(AggregateRoot[StaffId]):
    """薬局で勤務するスタッフ（薬剤師、調剤事務、管理栄養士、登録販売者等）の情報を管理するドメインエンティティ。"""

    id: StaffId
    corporate_id: CorporateId
    names: PersonNames
    qualifications: StaffQualifications = field(
        default_factory=StaffQualifications.empty
    )
    job_title: JobTitle | None = None
    code: StaffCode | None = None
    phone_number: StaffPhoneNumber | None = None
    email: StaffEmailAddress | None = None
    status: StaffStatus = StaffStatus.ACTIVE
    leave_reason: LeaveReason | None = None
    employment_type: EmploymentType = EmploymentType.REGULAR
    weekly_contract_hours: WeeklyContractHours | None = None

    affiliations: tuple[StoreAffiliation, ...] = ()
    work_conditions: tuple[StoreWorkCondition, ...] = ()

    # --- 自集約の不変条件 ---

    def validate(self) -> None:
        """所属履歴の期間や就業状態の整合性を検証する。"""
        self._ensure_primary_affiliations_never_overlap()
        self._ensure_same_store_affiliations_never_overlap()
        self._ensure_leave_status_consistency()
        for condition in self.work_conditions:
            if not any(
                affiliation.store_id == condition.store_id
                and affiliation.period.is_active_on(condition.effective_from)
                for affiliation in self.affiliations
            ):
                raise DomainValidationError(
                    "勤務条件の適用開始日は店舗の所属期間内にしてください。"
                )

    def record_work_conditions(
        self, conditions: tuple[StoreWorkCondition, ...], *, applied_on: date
    ) -> Self:
        """一括変更後の資格・所属と現在以降の契約時間上限を検証する。"""
        for condition in conditions:
            if condition.duty is StoreDuty.PHARMACIST and not self.is_pharmacist:
                raise DomainValidationError(
                    "薬剤師の従事区分には薬剤師資格が必要です。"
                )
            if (
                condition.duty is StoreDuty.REGISTERED_SELLER
                and not self.is_registered_seller
            ):
                raise DomainValidationError(
                    "登録販売者の従事区分には登録販売者資格が必要です。"
                )
        updated = replace(self, work_conditions=(*self.work_conditions, *conditions))
        updated.ensure_weekly_hours_within_contract(applied_on)
        return updated

    def ensure_weekly_hours_within_contract(self, applied_on: date) -> None:
        """変更日以降の各適用境界で、登録済み時間数の合計が契約時間以内か検証する。"""
        if self.weekly_contract_hours is None:
            return
        dates = {
            applied_on,
            *(
                item.effective_from
                for item in self.work_conditions
                if item.effective_from >= applied_on
            ),
            *(
                item.period.start_date
                for item in self.affiliations
                if item.period.start_date >= applied_on
            ),
        }
        for target in sorted(dates):
            total = sum(
                (
                    condition.weekly_hours.value
                    for store in {item.store_id for item in self.affiliations}
                    if (condition := self.work_condition_on(store, target)) is not None
                    and condition.weekly_hours is not None
                ),
                Decimal("0"),
            )
            if total > self.weekly_contract_hours.value:
                raise DomainValidationError(
                    f"店舗別の週勤務時間の合計（{total}時間）が週所定労働時間（{self.weekly_contract_hours.value}時間）を超えています。適用日: {target}"
                )

    def work_condition_on(
        self, store_id: StoreId, applied_on: date
    ) -> StoreWorkCondition | None:
        """対象日に所属する店舗の最新の適用条件を返す。同日訂正は後の記録を採用する。"""
        affiliation = next(
            (
                a
                for a in self.affiliations
                if a.store_id == store_id and a.period.is_active_on(applied_on)
            ),
            None,
        )
        if affiliation is None:
            return None
        candidates = [
            (item.effective_from, index, item)
            for index, item in enumerate(self.work_conditions)
            if item.store_id == store_id
            and affiliation.period.start_date <= item.effective_from <= applied_on
        ]
        return (
            max(candidates, key=lambda entry: (entry[0], entry[1]))[2]
            if candidates
            else None
        )

    def _ensure_leave_status_consistency(self) -> None:
        """休職状態と休職理由の整合性を検証する。"""
        if self.status == StaffStatus.ON_LEAVE and self.leave_reason is None:
            raise DomainValidationError("休職中のスタッフには休職理由が必要です。")
        if self.status != StaffStatus.ON_LEAVE and self.leave_reason is not None:
            raise DomainValidationError(
                "休職中以外のスタッフに休職理由は設定できません。"
            )

    @property
    def is_active(self) -> bool:
        """通常業務を行える稼働状態か判定する（休職中・退職時はFalse）。"""
        return self.status == StaffStatus.ACTIVE

    @property
    def is_on_leave(self) -> bool:
        """休職中か判定する。"""
        return self.status == StaffStatus.ON_LEAVE

    @property
    def is_employed(self) -> bool:
        """在籍中（退職していない）か判定する。"""
        return self.status != StaffStatus.RETIRED

    @property
    def effective_weekly_hours(self) -> Decimal:
        """実効稼働時間（週時間）。

        休職中や退職済みの場合は契約時間にかかわらず 0.0 時間となり、
        稼働中（ACTIVE）の場合のみ契約上の週所定労働時間を返す（未設定なら0.0時間）。
        """
        if self.status != StaffStatus.ACTIVE or self.weekly_contract_hours is None:
            return Decimal("0.0")
        return self.weekly_contract_hours.value

    def effective_full_time_equivalent(
        self, standard_hours: Decimal = Decimal("40.0")
    ) -> Decimal:
        """実効常勤換算比率（FTE）を算出する。

        休職中（育休・病休など）や退職済みのスタッフは施設基準上の稼働人員から
        除外されるため、契約時間にかかわらず 0.00 を返す。
        稼働中（ACTIVE）の場合のみ、週所定労働時間に基づく常勤換算比率を返す。
        """
        if self.status != StaffStatus.ACTIVE or self.weekly_contract_hours is None:
            return Decimal("0.00")
        return self.weekly_contract_hours.full_time_equivalent(standard_hours)

    def effective_is_full_time(
        self, threshold_hours: Decimal = Decimal("32.0")
    ) -> bool:
        """実効的に常勤要件（既定週32時間以上）を満たしているか判定する。"""
        if self.status != StaffStatus.ACTIVE or self.weekly_contract_hours is None:
            return False
        return self.weekly_contract_hours.is_full_time(threshold_hours)

    def _ensure_primary_affiliations_never_overlap(self) -> None:
        """主所属は店舗を問わず期間が重ならないことを検証する。"""
        primaries = [aff for aff in self.affiliations if aff.is_primary]
        if _has_overlapping_period(primaries):
            raise PrimaryAffiliationDuplicationError()

    def _ensure_same_store_affiliations_never_overlap(self) -> None:
        """同一店舗の所属は主所属・兼務を問わず期間が重ならないことを検証する。"""
        by_store: defaultdict[StoreId, list[StoreAffiliation]] = defaultdict(list)
        for affiliation in self.affiliations:
            by_store[affiliation.store_id].append(affiliation)
        for same_store in by_store.values():
            if _has_overlapping_period(same_store):
                raise ConcurrentStoreConflictError()

    # --- 権限・資格チェックの委譲プロパティ ---

    def has_qualification(self, profile_type: type[BaseQualificationProfile]) -> bool:
        return self.qualifications.has(profile_type)

    @property
    def is_pharmacist(self) -> bool:
        return self.has_qualification(PharmacistProfile)

    @property
    def is_dietitian(self) -> bool:
        return self.has_qualification(DietitianProfile)

    @property
    def is_registered_seller(self) -> bool:
        return self.has_qualification(RegisteredSellerProfile)

    @property
    def pharmacist_profile(self) -> PharmacistProfile | None:
        return self.qualifications.get(PharmacistProfile)

    # --- 所属に関する導出メソッド（現在の状態を計算する） ---

    def current_home_store_id(self, today: date) -> StoreId | None:
        """今日時点での主所属店舗を履歴から導出する

        主所属の期間重複は :meth:`validate` が構築時に禁止するため、
        該当する所属は高々1件であり、この導出は例外を送出しない。
        """
        return next(
            (
                aff.store_id
                for aff in self.affiliations
                if aff.is_primary and aff.period.is_active_on(today)
            ),
            None,
        )

    def current_concurrent_store_ids(self, today: date) -> frozenset[StoreId]:
        """今日時点で兼務している店舗一覧を履歴から導出する"""
        store_ids = [
            aff.store_id
            for aff in self.affiliations
            if not aff.is_primary and aff.period.is_active_on(today)
        ]
        return frozenset(store_ids)

    # --- ファクトリメソッド ---

    # --- その他のドメインメソッド（状態変更） ---

    def change_names(self, names: PersonNames) -> Self:
        """氏名を変更する"""

        return replace(self, names=names)

    def change_job_title(self, job_title: JobTitle | None) -> Self:
        """役職・肩書を変更する"""

        return replace(self, job_title=job_title)

    def update_qualifications(self, qualifications: StaffQualifications) -> Self:
        """資格情報を一括更新する（国家試験合格・追加取得等）"""

        return replace(self, qualifications=qualifications)

    def deactivate(self, retired_on: date) -> Self:
        """退職等に伴い無効化し、退職日以降に及ぶ所属をすべて退職日で打ち切る。

        退職日を必須にするのは、``is_active`` が日付を持たないフラグである一方、
        :meth:`current_home_store_id` が適用日ごとの導出だからである。
        フラグだけを倒すと所属期間が無期限のまま残り、退職後の日付でも所属店舗が
        返る。逆に導出側でフラグを見て打ち切ると、在籍していた**過去日**の所属まで
        引けなくなり、調剤録・監査の追跡が切れる。退職日をもともと日付つきの
        所属履歴へ書き込めば、導出は日付つき事実だけの全域関数のまま保たれる。

        すでに退職日以前で終了している所属はそのまま残す。無効化を繰り返した
        場合、所属はすでに閉じているので**より早い退職日が残る**（後から遅い日を
        渡しても期間は延びない）。復職後の所属は
        :class:`~app.domain.staff.services.StaffStoreAssignmentService` で改めて
        追加するため、再度の無効化はその新しい所属を閉じる。

        Raises:
            AffiliationDateConflictError: 退職日より後に開始する所属が残っている場合。
                期間を退職日で閉じると開始日が終了日を追い越すため、勝手に捨てず
                拒否する（未来の配属予約は退職の前に取り消す必要がある）。
        """
        if any(
            affiliation.period.start_date > retired_on
            for affiliation in self.affiliations
        ):
            raise AffiliationDateConflictError(
                "退職日より後に開始する所属履歴または予約が存在します。"
            )
        closed = tuple(
            affiliation.close(retired_on)
            if affiliation.period.end_date is None
            or affiliation.period.end_date > retired_on
            else affiliation
            for affiliation in self.affiliations
        )
        return replace(
            self,
            status=StaffStatus.RETIRED,
            leave_reason=None,
            affiliations=closed,
        )

    def activate(self) -> Self:
        """有効化（復職等）する。

        所属は復元しない。無効化時に閉じた所属をそのまま開き直すと、退職期間中も
        在籍していたことになる。復職後の配属は
        :class:`~app.domain.staff.services.StaffStoreAssignmentService` で改めて
        行う（どの店舗へ戻るかは復職時に決まる事実であり、退職前の所属から
        導出できない）。
        """

        return replace(
            self,
            status=StaffStatus.ACTIVE,
            leave_reason=None,
        )

    def start_leave(self, *, reason: LeaveReason, left_on: date) -> Self:
        """休職を開始する。所属履歴は維持しつつ稼働状態を非稼働とする。"""
        if self.status == StaffStatus.RETIRED:
            raise DomainValidationError("退職済みのスタッフは休職できません。")
        return replace(
            self,
            status=StaffStatus.ON_LEAVE,
            leave_reason=reason,
        )

    def return_from_leave(self) -> Self:
        """休職から復職する。"""
        if self.status != StaffStatus.ON_LEAVE:
            raise DomainValidationError("休職中ではないスタッフは復職できません。")
        return replace(
            self,
            status=StaffStatus.ACTIVE,
            leave_reason=None,
        )

    def change_employment_type(self, employment_type: EmploymentType) -> Self:
        """雇用形態を変更する"""
        return replace(self, employment_type=employment_type)

    def change_weekly_contract_hours(
        self, weekly_contract_hours: WeeklyContractHours | None, *, applied_on: date
    ) -> Self:
        """週所定労働時間を変更する"""
        updated = replace(self, weekly_contract_hours=weekly_contract_hours)
        updated.ensure_weekly_hours_within_contract(applied_on)
        return updated
