from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from itertools import pairwise
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.shared.person_name import PersonNames
from app.domain.staff.exceptions import (
    AffiliationDateConflictError,
    ConcurrentStoreConflictError,
    PrimaryAffiliationDuplicationError,
)
from app.domain.staff.primitives import (
    BaseQualificationProfile,
    DietitianProfile,
    JobTitle,
    PharmacistProfile,
    RegisteredSellerProfile,
    StaffCode,
    StaffEmailAddress,
    StaffId,
    StaffPhoneNumber,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.primitives import StoreId


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
    """スタッフエンティティ（集約ルート）"""

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
    is_active: bool = True

    # 💡 唯一の所属情報（home_store_id等は削除！）
    affiliations: tuple[StoreAffiliation, ...] = ()

    # --- 自集約の不変条件 ---

    def validate(self) -> None:
        """所属履歴の期間が重ならないことを検証する。

        ``Entity.__post_init__`` から呼ばれるため、``create()`` /
        ``dataclasses.replace()`` / Repositoryからの復元 / テストの直接構築の
        すべてがこの検証を通る。不正な所属履歴を持つ ``Staff`` は生成できない。
        """
        self._ensure_primary_affiliations_never_overlap()
        self._ensure_same_store_affiliations_never_overlap()

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

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        names: PersonNames,
        qualifications: StaffQualifications | None = None,
        job_title: JobTitle | None = None,
        code: StaffCode | None = None,
        phone_number: StaffPhoneNumber | None = None,
        email: StaffEmailAddress | None = None,
    ) -> Self:
        """新規スタッフを生成するファクトリメソッド"""
        return cls(
            id=StaffId.generate(),
            corporate_id=corporate_id,
            names=names,
            qualifications=qualifications or StaffQualifications.empty(),
            affiliations=(),
            job_title=job_title,
            code=code,
            phone_number=phone_number,
            email=email,
            is_active=True,
        )

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
        return replace(self, is_active=False, affiliations=closed)

    def activate(self) -> Self:
        """有効化（復職等）する。

        所属は復元しない。無効化時に閉じた所属をそのまま開き直すと、退職期間中も
        在籍していたことになる。復職後の配属は
        :class:`~app.domain.staff.services.StaffStoreAssignmentService` で改めて
        行う（どの店舗へ戻るかは復職時に決まる事実であり、退職前の所属から
        導出できない）。
        """

        return replace(self, is_active=True)
