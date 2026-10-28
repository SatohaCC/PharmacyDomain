"""receptionの単一値と列挙・検証規則。"""

from __future__ import annotations

import json

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.foundation.primitives.primitives import (
    BaseNonNegativeInt,
    BaseNormalizedString,
)


class ReceptionFingerprint(DomainPrimitive[str]):
    """受付に届いた業務データ全体または項目のSHA-256ハッシュ値。"""

    def validate(self) -> None:
        if len(self.value) != 64 or any(
            character not in "0123456789abcdef" for character in self.value
        ):
            raise DomainValidationError(
                "受付のハッシュ値は小文字16進数64桁で指定してください。"
            )


class ReceptionFieldPath(DomainPrimitive[str]):
    """受付データの差分を特定するフィールドパス。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("受付フィールドパスは空にできません。")


class ReceptionBillingCode(BaseNormalizedString):
    """受付原本に記録された算定加算コード。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("値は空にできません。")


class ReceptionBillingName(BaseNormalizedString):
    """受付原本に記録された算定加算名。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("値は空にできません。")


class ReceptionBillingPoints(BaseNonNegativeInt):
    """受付原本に記録された算定点数。"""


class ReceptionBillingQuantity(BaseNonNegativeInt):
    """受付原本に記録された算定数量。"""


class ReceptionOriginalJson(DomainPrimitive[str]):
    """受信原本を改変せず保持するJSON文字列。"""

    def validate(self) -> None:
        if not isinstance(self.value, str):
            raise DomainValidationError("受付原本はJSON文字列で指定してください。")
        try:
            json.loads(self.value)
        except (ValueError, TypeError) as exc:
            raise DomainValidationError("受付原本のJSONが不正です。") from exc
