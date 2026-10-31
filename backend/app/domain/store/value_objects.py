"""storeの複合値と参照スナップショット。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import ClassVar, Final

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.identity.identifiers import VendorOperatorId
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.staff.identifiers import StaffId
from app.domain.store.identifiers import StoreId
from app.domain.store.primitives import (
    BusinessHoursNote,
    BusinessWeekday,
    NarcoticsLicenseNumber,
    PharmacyLicenseNumber,
    StoreAddressLine,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StorePhoneNumber,
    StorePostalCode,
    StoreStatus,
    StoreStatusReason,
)

#: ``date.weekday()`` が返す番号との対応。
#:
#: 列挙の並び順から導くと（``list(BusinessWeekday)[index]``）、曜日を並べ替えた
#: 瞬間に全店舗の開局判定が1日ずれる。番号付けを決めているのは標準ライブラリ
#: なので、対応を表として持つ。
_WEEKDAY_BY_INDEX: Final[Mapping[int, BusinessWeekday]] = {
    0: BusinessWeekday.MONDAY,
    1: BusinessWeekday.TUESDAY,
    2: BusinessWeekday.WEDNESDAY,
    3: BusinessWeekday.THURSDAY,
    4: BusinessWeekday.FRIDAY,
    5: BusinessWeekday.SATURDAY,
    6: BusinessWeekday.SUNDAY,
}


#: 時間帯の終端に置いたときだけ「その日の終わり（24:00）」を表す時刻。
#:
#: ``time`` は0時から24時未満しか表せないので、終端の24:00を素直には書けない。
#: 開始時刻としての ``00:00`` はそのまま0時を指し、終端に現れたときだけ24時を
#: 指す、という約束をここ1箇所に置く。
_END_OF_DAY: Final = time(0, 0)


def weekday_of(target: date) -> BusinessWeekday:
    """日付の曜日を返す。"""
    return _WEEKDAY_BY_INDEX[target.weekday()]


@dataclass(frozen=True, kw_only=True)
class BusinessHourSlot(ValueObject):
    """1日のうち連続して開いている時間帯。

    終了時刻を含まない半開区間 ``[opens_at, closes_at)`` とする。資格や任命の
    期間は終了日を**含む**閉区間だが、時刻はここで向きが違う。昼休みを挟む
    9:00-13:00 と 14:00-19:00 を閉区間で持つと、13:00 と 14:00 が2つの時間帯に
    属したり属さなかったりして、同じ時刻が「開いている」とも「閉じている」とも
    言える状態になる。

    日をまたぐ時間帯は1件で持たない。22:00から翌2:00まで開ける場合は、その日の
    22:00-24:00 と翌日の 00:00-02:00 の2件に分ける。1件で持つと、判定する時刻が
    どちらの日に属するかが時間帯の中身に依存し、特例日の上書きも効かなくなる。
    """

    opens_at: time
    closes_at: time

    def validate(self) -> None:
        """タイムゾーン無しの時刻と、開始より後の終了を要求する。"""
        if self.opens_at.tzinfo is not None or self.closes_at.tzinfo is not None:
            raise DomainValidationError(
                "開局時間帯の時刻にタイムゾーンは指定できません。"
            )
        if self.closes_at != _END_OF_DAY and self.closes_at <= self.opens_at:
            raise DomainValidationError(
                "開局時間帯の終了時刻は開始時刻より後にしてください。"
            )

    @property
    def closes_at_end_of_day(self) -> bool:
        """終了時刻がその日の24時か。"""
        return self.closes_at == _END_OF_DAY

    def contains(self, at: time) -> bool:
        """時刻がこの時間帯に含まれるか。"""
        if at < self.opens_at:
            return False
        return self.closes_at_end_of_day or at < self.closes_at

    def overlaps(self, other: BusinessHourSlot) -> bool:
        """2つの時間帯が重なるか。"""
        return (other.closes_at_end_of_day or self.opens_at < other.closes_at) and (
            self.closes_at_end_of_day or other.opens_at < self.closes_at
        )


def _validate_slots(slots: tuple[BusinessHourSlot, ...], *, label: str) -> None:
    """同じ日の時間帯どうしが重ならないことを要求する。"""
    for index, slot in enumerate(slots):
        for other in slots[index + 1 :]:
            if slot.overlaps(other):
                raise DomainValidationError(f"{label}の開局時間帯が重なっています。")


@dataclass(frozen=True, kw_only=True)
class WeekdayBusinessHours(ValueObject):
    """1つの曜日の開局予定。時間帯が空なら定休日。"""

    weekday: BusinessWeekday
    slots: tuple[BusinessHourSlot, ...] = ()

    def validate(self) -> None:
        """同じ曜日の時間帯が重ならないことを要求する。"""
        _validate_slots(self.slots, label=self.weekday.value)


@dataclass(frozen=True, kw_only=True)
class BusinessDayException(ValueObject):
    """日付を指定して週次の予定を上書きする。時間帯が空なら臨時休業。

    祝日をここに登録する。祝日の判定を内蔵しないのは、日本の祝日が法改正で
    変わるうえ春分・秋分は毎年の天文計算で決まるからで、暦を抱えるとドメインが
    毎年古くなる。祝日か臨時休業かは ``note`` に書く。
    """

    on: date
    slots: tuple[BusinessHourSlot, ...] = ()
    note: BusinessHoursNote | None = None

    def validate(self) -> None:
        """同じ日の時間帯が重ならないことを要求する。"""
        _validate_slots(self.slots, label=self.on.isoformat())


@dataclass(frozen=True, kw_only=True)
class BusinessHours(ValueObject):
    """週次の開局予定と、日付を指定した例外。"""

    weekly: tuple[WeekdayBusinessHours, ...]
    exceptions: tuple[BusinessDayException, ...] = ()

    def validate(self) -> None:
        """全曜日の宣言と、1日以上の開局を要求する。

        宣言の無い曜日を定休日として扱わない。既定を「休み」に倒すと、曜日を1つ
        書き漏らした店舗が、登録できたうえで静かにその曜日だけ閉まる。開局時間は
        店舗ごとに一度作るものなので、7行書かせるほうが安い。

        全曜日が空の予定も拒否する。営業していないことは店舗の状態（休止・閉局）
        が表すので、同じ事実を2通りで表せるようにしない。
        """
        declared = [item.weekday for item in self.weekly]
        if len(set(declared)) != len(declared):
            raise DomainValidationError("同じ曜日の開局予定が重複しています。")
        if set(declared) != set(BusinessWeekday):
            raise DomainValidationError("開局予定は全ての曜日を指定してください。")
        if not any(item.slots for item in self.weekly):
            raise DomainValidationError(
                "開局予定には、少なくとも1日の開局時間帯が必要です。"
            )
        days = [item.on for item in self.exceptions]
        if len(set(days)) != len(days):
            raise DomainValidationError("同じ日付の特例が重複しています。")

    def slots_on(self, on: date) -> tuple[BusinessHourSlot, ...]:
        """その日に適用される開局時間帯を返す。

        例外を出さない全域関数にする。呼び出し側は「開いている時間帯の一覧」を
        受け取るだけでよく、曜日が見つからない場合を分岐させない。
        """
        for item in self.exceptions:
            if item.on == on:
                return item.slots
        target = weekday_of(on)
        for weekly in self.weekly:
            if weekly.weekday == target:
                return weekly.slots
        return ()

    def is_open_at(self, *, on: date, at: time) -> bool:
        """その日時に開いているか。"""
        return any(slot.contains(at) for slot in self.slots_on(on))


@dataclass(frozen=True, kw_only=True)
class StoreStatusChange(ValueObject):
    """店舗の状態遷移とその操作者。"""

    before: StoreStatus
    after: StoreStatus
    reason: StoreStatusReason
    recorded_at: datetime
    person_id: AccountPersonId | None = None
    account_id: UserAccountId | None = None
    operator_id: VendorOperatorId | None = None

    def validate(self) -> None:
        """記録日時にタイムゾーンを要求する。"""
        if self.recorded_at.utcoffset() is None:
            raise DomainValidationError("記録日時にはタイムゾーンが必要です。")
        if (
            self.operator_id is None
            and (self.person_id is None or self.account_id is None)
        ) or (
            self.operator_id is not None
            and (self.person_id is not None or self.account_id is not None)
        ):
            raise DomainValidationError(
                "店舗状態履歴の操作者には、運営者IDまたは本人・アカウントが必要です。"
            )


@dataclass(frozen=True, kw_only=True)
class ManagerAssignmentPeriod(ValueObject):
    """終了日を含む任命期間。"""

    starts_on: date
    ends_on: date | None = None

    def validate(self) -> None:
        """開始前の終了を拒否する。"""
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise DomainValidationError("任命の終了日は開始日以降にしてください。")

    def contains(self, target_date: date) -> bool:
        """適用日が任命期間に含まれるか。"""
        return self.starts_on <= target_date and (
            self.ends_on is None or target_date <= self.ends_on
        )


@dataclass(frozen=True, kw_only=True)
class ManagerStaffAffiliation(ValueObject):
    """任命期間との包含関係を判断するための所属期間。"""

    store_id: StoreId
    starts_on: date
    ends_on: date | None

    def validate(self) -> None:
        """期間が逆転していないことを保証する。"""
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise DomainValidationError(
                "所属終了日は所属開始日以降で指定してください。"
            )


@dataclass(frozen=True, kw_only=True)
class ManagerStaffSource(ValueObject):
    """スタッフ実装を保持せず、任命の判断材料を固定する。"""

    staff_id: StaffId
    corporate_id: CorporateId
    staff_is_active: bool
    has_pharmacist: bool
    affiliations: tuple[ManagerStaffAffiliation, ...]


@dataclass(frozen=True, kw_only=True)
class StoreNames(ValueObject):
    """店舗名の一式（正式名称・フリガナ・ローマ字）"""

    name: StoreName
    kana: StoreNameKana
    romaji: StoreNameRomaji | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "name": "正式名称",
        "kana": "フリガナ",
        "romaji": "ローマ字",
    }


@dataclass(frozen=True, kw_only=True)
class StoreAddress(ValueObject):
    """所在地情報（郵便番号と住所）。"""

    postal_code: StorePostalCode
    address: StoreAddressLine  # 例: "〇〇1-2-3"

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "postal_code": "郵便番号",
        "address": "住所",
    }


@dataclass(frozen=True, kw_only=True)
class ContactInfo(ValueObject):
    """連絡先情報。"""

    phone_number: StorePhoneNumber
    fax_number: StoreFaxNumber | None = None
    email: StoreEmailAddress | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "phone_number": "電話番号",
        "fax_number": "FAX番号",
        "email": "メールアドレス",
    }

    def validate(self) -> None:
        """必須の電話番号が空でないことを検証する。"""
        if not self.phone_number.value:
            raise DomainValidationError("電話番号は空にできません。")


@dataclass(frozen=True, kw_only=True)
class PharmacyLicense(ValueObject):
    """薬局開設許可情報（薬機法対応）。"""

    number: PharmacyLicenseNumber
    valid_from: date
    valid_to: date

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "number": "薬局開設許可番号",
        "valid_from": "許可有効期間開始日",
        "valid_to": "許可有効期間満了日",
    }

    def validate(self) -> None:
        """開始日が満了日以前であることを検証する。"""
        if self.valid_from > self.valid_to:
            raise DomainValidationError(
                "薬局開設許可の有効期間開始日は満了日以前である必要があります。"
            )

    def is_effective_on(self, target_date: date) -> bool:
        """指定された業務日に許可が有効（両端を含む）であるかを判定する。"""
        return self.valid_from <= target_date <= self.valid_to


@dataclass(frozen=True, kw_only=True)
class NarcoticsRetailerLicense(ValueObject):
    """麻薬小売業者免許情報（麻薬及び向精神薬取締法対応）。"""

    number: NarcoticsLicenseNumber
    valid_from: date
    valid_to: date

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "number": "麻薬小売業者免許番号",
        "valid_from": "免許有効期間開始日",
        "valid_to": "免許有効期間満了日",
    }

    def validate(self) -> None:
        """原本満了日が免許日の属する年の翌々年12月31日であることを検証する。"""
        if self.valid_from > self.valid_to:
            raise DomainValidationError(
                "麻薬小売業者免許の有効期間開始日は満了日以前である必要があります。"
            )
        statutory_expiry = date(self.valid_from.year + 2, 12, 31)
        if self.valid_to != statutory_expiry:
            raise DomainValidationError(
                f"麻薬小売業者免許の満了日は免許日の翌々年12月31日（{statutory_expiry}）である必要があります。"
            )

    def is_effective_on(self, target_date: date) -> bool:
        """指定された業務日に免許が有効（両端を含む）であるかを判定する。"""
        return self.valid_from <= target_date <= self.valid_to


@dataclass(frozen=True, kw_only=True)
class StoreLicenses(ValueObject):
    """店舗の許認可一式。"""

    pharmacy_license: PharmacyLicense
    narcotics_retailer_license: NarcoticsRetailerLicense | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "pharmacy_license": "薬局開設許可",
        "narcotics_retailer_license": "麻薬小売業者免許",
    }


@dataclass(frozen=True, kw_only=True)
class StorePolicy(ValueObject):
    """店舗ポリシー設定（None は法人値を採用）。"""

    require_prescription_audit: bool | None = None
    prohibit_self_verification: bool | None = None
