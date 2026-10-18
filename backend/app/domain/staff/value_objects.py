"""staffの複合値と参照スナップショット。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from typing import ClassVar, Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.staff.primitives import (
    CertificationIssuingOrganizationName,
    DietitianRegistrationNumber,
    InsurancePharmacistRegistrationNumber,
    PharmacistLicenseNumber,
    SellerRegistrationNumber,
    StaffQualification,
)
from app.domain.store.identifiers import StoreId


@dataclass(frozen=True, kw_only=True)
class StoreSource(ValueObject):
    """店舗の同一性、法人、閉局事実だけを保持する。"""

    store_id: StoreId
    corporate_id: CorporateId
    is_closed: bool


@dataclass(frozen=True, kw_only=True)
class BaseQualificationProfile(ValueObject, ABC):
    """資格プロファイルの共通基底クラス"""

    @property
    @abstractmethod
    def qualification_type(self) -> StaffQualification:
        """対応する法的資格区分（派生クラスで必ず実装を強制）"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """画面や名札での表示用名称（例: '薬剤師', '管理栄養士'）"""
        pass


@dataclass(frozen=True, kw_only=True)
class InsurancePharmacistRegistration(ValueObject):
    """保険薬剤師登録情報"""

    registration_number: InsurancePharmacistRegistrationNumber
    registration_date: date  # 登録年月日

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "registration_number": "保険薬剤師登録番号",
        "registration_date": "登録年月日",
    }


@dataclass(frozen=True, kw_only=True)
class CertifiedPharmacistInfo(ValueObject):
    """研修認定薬剤師の認定情報"""

    issuing_organization: CertificationIssuingOrganizationName
    expiration_date: date  # 有効期限（超重要: 期限切れアラートに必須）

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "issuing_organization": "認定機関",
        "expiration_date": "有効期限",
    }

    def is_valid_on(self, target_date: date) -> bool:
        """指定した日付時点で認定が有効か判定する"""
        return target_date <= self.expiration_date


@dataclass(frozen=True, kw_only=True)
class HealthSupportPharmacistInfo(ValueObject):
    """健康サポート薬剤師研修の修了情報"""

    completion_date: date  # 修了年月日

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"completion_date": "修了年月日"}


@dataclass(frozen=True, kw_only=True)
class StaffQualifications(ValueObject):
    """保有資格のコレクション（ファーストクラスコレクション）

    何個の資格（ダブル・トリプルライセンス）でも保持でき、
    新しい資格クラスが増えてもこのクラス自体を変更する必要がない。
    """

    _items: tuple[BaseQualificationProfile, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"_items": "資格プロファイル"}

    def validate(self) -> None:
        """資格区分が正しく重複していないことを検証する。"""
        for item in self._items:
            if not isinstance(item.qualification_type, StaffQualification):
                raise DomainValidationError("資格プロファイルの資格区分が不正です。")

        # 同一の法的資格区分が重複して登録されていないか検証
        qualification_types = [item.qualification_type for item in self._items]
        if len(qualification_types) != len(set(qualification_types)):
            raise DomainValidationError("同一の資格区分が重複して指定されています。")

    @property
    def profiles(self) -> tuple[BaseQualificationProfile, ...]:
        """保持している全プロファイルのタプル"""
        return self._items

    def get[P: BaseQualificationProfile](self, profile_type: type[P]) -> P | None:
        """指定した型のプロファイルを取得する（型推論が効く）"""
        for item in self._items:
            if isinstance(item, profile_type):
                return item
        return None

    def has(self, profile_type: type[BaseQualificationProfile]) -> bool:
        """指定した資格を保有しているか判定する"""
        return self.get(profile_type) is not None

    @classmethod
    def from_profiles(cls, *profiles: BaseQualificationProfile) -> Self:
        """可変長引数から生成するファクトリ"""
        return cls(_items=tuple(profiles))

    @classmethod
    def empty(cls) -> Self:
        """資格なし（医療事務等）を生成"""
        return cls(_items=())


@dataclass(frozen=True, kw_only=True)
class AffiliationPeriod(ValueObject):
    """所属期間（いつからいつまで）を表す Value Object"""

    start_date: date
    end_date: date | None = None  # None の場合は「現在も所属中」を意味する

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "start_date": "開始日",
        "end_date": "終了日",
    }

    def validate(self) -> None:
        """開始日と終了日の前後関係を検証する。"""
        if self.end_date and self.start_date > self.end_date:
            raise DomainValidationError("開始日は終了日より前である必要があります。")

    def is_active_on(self, target_date: date) -> bool:
        """指定した日付時点でこの期間が有効（所属中）かどうか"""
        if self.end_date is None:
            return self.start_date <= target_date
        return self.start_date <= target_date <= self.end_date

    def overlaps(self, other: AffiliationPeriod) -> bool:
        """この期間と別の期間が1日でも重なるかを返す。

        終了日を含む閉区間 ``[start_date, end_date]`` として扱い、
        ``end_date`` が ``None`` の期間は無期限（未来側に終わりがない）とみなす。
        """
        self_ends_before_other_starts = (
            self.end_date is not None and self.end_date < other.start_date
        )
        other_ends_before_self_starts = (
            other.end_date is not None and other.end_date < self.start_date
        )
        return not (self_ends_before_other_starts or other_ends_before_self_starts)


@dataclass(frozen=True, kw_only=True)
class StoreAffiliation(ValueObject):
    """1つの店舗への所属レコード（履歴書の1行に相当）"""

    store_id: StoreId
    period: AffiliationPeriod
    is_primary: bool  # True: 主所属, False: 兼務・応援

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "store_id": "店舗ID",
        "period": "所属期間",
        "is_primary": "主所属区分",
    }

    def close(self, end_date: date) -> StoreAffiliation:
        """所属期間を終了する（異動や兼務解除の際に呼ばれる）"""
        new_period = replace(self.period, end_date=end_date)
        return replace(self, period=new_period)


@dataclass(frozen=True, kw_only=True)
class PharmacistProfile(BaseQualificationProfile):
    """薬剤師資格（レセプト請求・施設基準に必要な情報を網羅）"""

    license_number: PharmacistLicenseNumber  # 薬剤師名簿登録番号（国家資格）

    # 保険調剤を行うための登録（※これがないと調剤業務ができない）
    insurance_registration: InsurancePharmacistRegistration | None = None

    # 施設基準・加算要件となる付加認定
    certified_info: CertifiedPharmacistInfo | None = None
    health_support_info: HealthSupportPharmacistInfo | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "license_number": "薬剤師名簿登録番号",
        "insurance_registration": "保険薬剤師登録情報",
        "certified_info": "研修認定薬剤師情報",
        "health_support_info": "健康サポート薬剤師情報",
    }

    @property
    def qualification_type(self) -> StaffQualification:
        return StaffQualification.PHARMACIST

    @property
    def display_name(self) -> str:
        return "薬剤師"

    # --- ドメインロジック（判定用ヘルパー） ---

    def can_bill_insurance(self) -> bool:
        """保険調剤（レセプト請求）が可能か"""
        return self.insurance_registration is not None

    def is_certified_on(self, today: date) -> bool:
        """今日時点で有効な研修認定薬剤師か"""
        if not self.certified_info:
            return False
        return self.certified_info.is_valid_on(today)


@dataclass(frozen=True, kw_only=True)
class DietitianProfile(BaseQualificationProfile):
    """管理栄養士・栄養士資格"""

    registration_number: DietitianRegistrationNumber
    is_registered_dietitian: bool = True

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "registration_number": "登録番号",
        "is_registered_dietitian": "管理栄養士区分",
    }

    @property
    def qualification_type(self) -> StaffQualification:
        return (
            StaffQualification.REGISTERED_DIETITIAN
            if self.is_registered_dietitian
            else StaffQualification.DIETITIAN
        )

    @property
    def display_name(self) -> str:
        return "管理栄養士" if self.is_registered_dietitian else "栄養士"


@dataclass(frozen=True, kw_only=True)
class RegisteredSellerProfile(BaseQualificationProfile):
    """登録販売者資格"""

    registration_number: SellerRegistrationNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {"registration_number": "登録番号"}

    @property
    def qualification_type(self) -> StaffQualification:
        return StaffQualification.REGISTERED_SELLER

    @property
    def display_name(self) -> str:
        return "登録販売者"
