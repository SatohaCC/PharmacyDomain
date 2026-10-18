"""care_eventの単一値と列挙・検証規則。"""

from __future__ import annotations

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import BaseAwareTimestamp, BaseFreeText


class EventTypeName(BaseFreeText):
    """イベント種別の表示名。"""


class EventTypeStandardCode(BaseFreeText):
    """標準イベント種別の安定したコード。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("標準イベント種別コードは空にできません。")
        if len(self.value) > 80:
            raise DomainValidationError("標準イベント種別コードは80文字以内です。")


class EventOccurredTimestamp(BaseAwareTimestamp):
    """イベントの発生日時。"""

    timestamp_name = "イベント発生日時"


class EventCreatedTimestamp(BaseAwareTimestamp):
    """イベントの登録日時。"""

    timestamp_name = "イベント登録日時"
