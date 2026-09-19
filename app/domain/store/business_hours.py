"""店舗の開局時間と、ある日時に開いているかの判定。

判定はタイムゾーンを持たない「日付と時刻」で行う。UTCとJSTのどちらで数えるかは
業務日の決め方と同じ問題で、Domainが各所で持つとずれる。変換は呼び出し側
（Application層の業務時計）に委ね、ここでは渡された日付と時刻だけを見る。
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, time
from enum import StrEnum
from typing import Final

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseNormalizedString
from app.domain.foundation.value_object import ValueObject


class BusinessWeekday(StrEnum):
    """開局予定を組み立てる曜日。"""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


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


class StoreOpeningState(StrEnum):
    """ある日時に店舗が開いているか。"""

    OPEN = "open"
    CLOSED = "closed"
    #: 開局時間が未登録で判定できない。
    UNKNOWN = "unknown"


class BusinessHoursNote(BaseNormalizedString):
    """特例日の理由（「年末年始」「臨時休業」など）。"""

    def validate(self) -> None:
        """空でない100文字以内を要求する。"""
        if not self.value or len(self.value) > 100:
            raise DomainValidationError(
                "特例日の理由は1から100文字で指定してください。"
            )


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
        left_end = time.max if self.closes_at_end_of_day else self.closes_at
        right_end = time.max if other.closes_at_end_of_day else other.closes_at
        return self.opens_at < right_end and other.opens_at < left_end


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


__all__ = [
    "BusinessDayException",
    "BusinessHourSlot",
    "BusinessHours",
    "BusinessHoursNote",
    "BusinessWeekday",
    "StoreOpeningState",
    "WeekdayBusinessHours",
    "weekday_of",
]
