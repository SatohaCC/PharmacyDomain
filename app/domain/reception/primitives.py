"""Receptionコンテキストの識別子と監査プリミティブ。"""

from __future__ import annotations

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.base import DomainPrimitive


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
