from dataclasses import dataclass, field, replace
from datetime import date
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.base.domain.primitives.primitives import (
    BaseEmailAddress,
    BaseTelephoneNumber,
)
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.staff.exceptions import PrimaryAffiliationDuplicationError
from app.domain.staff.primitives import (
    BaseQualificationProfile,
    DietitianProfile,
    JobTitle,
    PharmacistProfile,
    RegisteredSellerProfile,
    StaffCode,
    StaffId,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.primitives import StoreId


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
    phone_number: BaseTelephoneNumber | None = None
    email: BaseEmailAddress | None = None
    is_active: bool = True

    # 💡 唯一の所属情報（home_store_id等は削除！）
    affiliations: tuple[StoreAffiliation, ...] = ()

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

    def _active_primary_affiliations(
        self, target_date: date
    ) -> tuple[StoreAffiliation, ...]:
        return tuple(
            aff
            for aff in self.affiliations
            if aff.is_primary and aff.period.is_active_on(target_date)
        )

    def current_home_store_id(self, today: date) -> StoreId | None:
        """今日時点での主所属店舗を履歴から導出する"""
        active_affiliations = self._active_primary_affiliations(today)
        if len(active_affiliations) > 1:
            raise PrimaryAffiliationDuplicationError(
                "同じ日付に主所属店舗を複数持てません。"
            )
        return active_affiliations[0].store_id if active_affiliations else None

    def current_concurrent_store_ids(self, today: date) -> frozenset[StoreId]:
        """今日時点で兼務している店舗一覧を履歴から導出する"""
        store_ids = [
            aff.store_id
            for aff in self.affiliations
            if not aff.is_primary and aff.period.is_active_on(today)
        ]
        return frozenset(store_ids)

    def can_access_store(self, store_id: StoreId, today: date) -> bool:
        """指定された店舗での業務（ログイン等）が可能か判定する"""
        if not self.is_active:
            return False
        return self.current_home_store_id(
            today
        ) == store_id or store_id in self.current_concurrent_store_ids(today)

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
        phone_number: BaseTelephoneNumber | None = None,
        email: BaseEmailAddress | None = None,
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

    def deactivate(self) -> Self:
        """退職等に伴い無効化する"""

        return replace(self, is_active=False)

    def activate(self) -> Self:
        """有効化（復職等）する"""

        return replace(self, is_active=True)
