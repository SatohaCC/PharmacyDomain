from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from typing import ClassVar, Self

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseEmailAddress,
    BaseNormalizedString,
    BaseTelephoneNumber,
    EntityUUID,
)
from app.domain.foundation.value_object import ValueObject
from app.domain.store.primitives import StoreId


class StaffId(EntityUUID):
    """スタッフ識別子（UUIDv7）"""

    identifier_name = "スタッフID"


class StaffCode(BaseNormalizedString):
    """社員番号・スタッフコード（例: STF-001）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("スタッフコードは空にできません。")
        if len(self.value) > 20:
            raise DomainValidationError(
                "スタッフコードは20文字以内で指定してください。"
            )


class JobTitle(BaseNormalizedString):
    """薬局・法人が自由に設定する役職・肩書（例: '薬局長', 'チーフクラーク', 'エリア長'）"""

    def validate(self) -> None:
        if len(self.value) > 50:
            raise DomainValidationError("役職名は50文字以内で指定してください。")


class StaffQualification(StrEnum):
    """法的資格区分（システム・薬機法・診療報酬上の固定Enum）

    システムのビジネスロジック（処方鑑査権限、調剤録署名、特定保健指導担当、
    免許番号の必須チェック等）の判定に使用する。
    国の法改正がない限り静的に管理される。
    """

    PHARMACIST = "pharmacist"  # 薬剤師（調剤・鑑査・服薬指導・管理薬剤師要件）
    REGISTERED_SELLER = "registered_seller"  # 登録販売者（第2類・第3類医薬品の販売）
    REGISTERED_DIETITIAN = (
        "registered_dietitian"  # 管理栄養士（栄養ケア指導・特定保健指導）
    )
    DIETITIAN = "dietitian"  # 栄養士
    NONE = "none"  # 資格なし（医療事務・調剤補助・本部スタッフ等）

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称"""
        labels = {
            self.PHARMACIST: "薬剤師",
            self.REGISTERED_SELLER: "登録販売者",
            self.REGISTERED_DIETITIAN: "管理栄養士",
            self.DIETITIAN: "栄養士",
            self.NONE: "資格なし（医療事務・調剤補助等）",
        }
        return labels[self]

    @property
    def is_pharmacist(self) -> bool:
        """薬剤師かどうか"""
        return self == StaffQualification.PHARMACIST

    @property
    def is_dietitian(self) -> bool:
        """栄養士（管理栄養士含む）かどうか"""
        return self in (
            StaffQualification.REGISTERED_DIETITIAN,
            StaffQualification.DIETITIAN,
        )

    @property
    def has_license_number(self) -> bool:
        """公的な登録番号・免許番号が存在する資格か"""
        return self != StaffQualification.NONE


# --- 各資格の番号VO ---


class PharmacistLicenseNumber(BaseNormalizedString):
    """薬剤師名簿登録番号（半角数字6〜7桁）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("薬剤師名簿登録番号は空にできません。")
        if not re.fullmatch(r"[0-9]{6,7}", self.value):
            raise DomainValidationError(
                "薬剤師名簿登録番号は半角数字6桁または7桁で入力してください。"
            )


class DietitianRegistrationNumber(BaseNormalizedString):
    """管理栄養士登録番号 / 栄養士免許番号（半角数字5〜8桁）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("登録番号は空にできません。")
        if not re.fullmatch(r"[0-9]{5,8}", self.value):
            raise DomainValidationError(
                "栄養士登録番号は半角数字5〜8桁で入力してください。"
            )


class SellerRegistrationNumber(BaseNormalizedString):
    """販売従事登録番号（登録販売者の都道府県登録番号）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("販売従事登録番号は空にできません。")
        if len(self.value) > 20:
            raise DomainValidationError(
                "販売従事登録番号は20文字以内で指定してください。"
            )


class StaffPhoneNumber(BaseTelephoneNumber):
    """スタッフの連絡先電話番号。"""

    field_name = "電話番号"


class StaffEmailAddress(BaseEmailAddress):
    """スタッフの連絡先メールアドレス。"""


class InsurancePharmacistRegistrationNumber(BaseNormalizedString):
    """保険薬剤師登録番号。"""


class CertificationIssuingOrganizationName(BaseNormalizedString):
    """薬剤師認定を発行した機関名。"""


# --- 資格プロファイル抽象基底クラス ---


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


# --- 個別の資格プロファイル（抽象プロパティを具体的に実装） ---
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


# --- ファーストクラスコレクション ---


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
