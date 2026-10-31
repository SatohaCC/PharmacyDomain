"""staffの単一値と列挙・検証規則。"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseEmailAddress,
    BaseNonNegativeDecimal,
    BaseNormalizedString,
    BaseTelephoneNumber,
)


class EmploymentType(StrEnum):
    """スタッフの雇用形態（労働契約区分）。"""

    REGULAR = "regular"  # 正社員（常勤・無期雇用）
    FIXED_TERM = "fixed_term"  # 契約社員（有期雇用）
    PART_TIME = "part_time"  # パート・アルバイト（非常勤・短時間）
    DISPATCHED = "dispatched"  # 派遣スタッフ

    @property
    def label(self) -> str:
        labels = {
            self.REGULAR: "正社員",
            self.FIXED_TERM: "契約社員",
            self.PART_TIME: "パート・アルバイト",
            self.DISPATCHED: "派遣スタッフ",
        }
        return labels[self]


class StaffStatus(StrEnum):
    """スタッフの就業状態。"""

    ACTIVE = "active"  # 通常稼働中
    ON_LEAVE = "on_leave"  # 休職中（産前産後・育児・介護・傷病等）
    RETIRED = "retired"  # 退職済み

    @property
    def label(self) -> str:
        labels = {
            self.ACTIVE: "稼働中",
            self.ON_LEAVE: "休職中",
            self.RETIRED: "退職",
        }
        return labels[self]


class LeaveReason(StrEnum):
    """休職理由。"""

    MATERNITY = "maternity"  # 産前産後休業
    CHILDCARE = "childcare"  # 育児休業
    FAMILY_CARE = "family_care"  # 介護休業
    INJURY_ILLNESS = "injury_illness"  # 私傷病休職
    OTHER = "other"  # その他休職

    @property
    def label(self) -> str:
        labels = {
            self.MATERNITY: "産前産後休業",
            self.CHILDCARE: "育児休業",
            self.FAMILY_CARE: "介護休業",
            self.INJURY_ILLNESS: "傷病休職",
            self.OTHER: "その他休職",
        }
        return labels[self]


class WeeklyContractHours(BaseNonNegativeDecimal):
    """週所定労働時間（時間単位）。

    スポット応援（ヘルプ）要員として事前届出・登録を行う場合など、
    契約上の基本所定労働時間が0時間となる場合も許容する（0.0〜80.0時間）。
    """

    max_integer_digits: ClassVar[int] = 2
    max_decimal_places: ClassVar[int] = 2
    quantity_name: ClassVar[str] = "週所定労働時間"

    def validate(self) -> None:
        if not isinstance(self.value, Decimal):
            raise DomainValidationError(
                f"{self.quantity_name}は数値である必要があります。"
            )
        if not self.value.is_finite():
            raise DomainValidationError(
                f"{self.quantity_name}は有限の数値である必要があります。"
            )
        if self.value < Decimal("0"):
            raise DomainValidationError(
                "週所定労働時間は0以上の値である必要があります。"
            )
        if self.value > Decimal("80.0"):
            raise DomainValidationError(
                "週所定労働時間は80時間以内で指定してください。"
            )
        self._ensure_digits_within_limit()

    def full_time_equivalent(
        self, standard_hours: Decimal = Decimal("40.0")
    ) -> Decimal:
        """基準労働時間（既定40時間）に対する常勤換算比率を算出する。"""
        if standard_hours <= Decimal("0"):
            raise DomainValidationError(
                "基準労働時間は0より大きい値である必要があります。"
            )
        return (self.value / standard_hours).quantize(Decimal("0.01"))

    def is_full_time(self, threshold_hours: Decimal = Decimal("32.0")) -> bool:
        """常勤要件（既定週32時間以上）を満たすか判定する。"""
        return self.value >= threshold_hours


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
