from __future__ import annotations

import re
from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseEmailAddress,
    BaseNormalizedString,
    BaseTelephoneNumber,
)


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


# --- 個別の資格プロファイル（抽象プロパティを具体的に実装） ---


# --- ファーストクラスコレクション ---
