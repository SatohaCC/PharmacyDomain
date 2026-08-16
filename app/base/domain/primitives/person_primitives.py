import re
import unicodedata
from dataclasses import dataclass
from typing import ClassVar

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import BaseNormalizedString


@dataclass(frozen=True)
class BasePersonName(BaseNormalizedString):
    """人名（漢字・アルファベット等）の基底プリミティブ。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("氏名は空にできません。")
        if len(self.value) > 50:
            raise DomainValidationError("氏名は50文字以内で入力してください。")


@dataclass(frozen=True)
class BasePersonNameKana(BaseNormalizedString):
    """人名（フリガナ・全角カタカナ）の基底プリミティブ。

    空白の正規化に加え、NFKCにより半角カナを全角カタカナへ変換します。
    """

    # 全角カタカナ（小書き・ヵ・ヶを含む）、長音符(ー)、中黒(・)、スペースを許容する正規表現
    KANA_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[ァ-ヶー・\s]+$")

    def _normalize(self, value: str) -> str:
        normalized = super()._normalize(value)
        return unicodedata.normalize("NFKC", normalized)

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("氏名（カナ）は空にできません。")
        if len(self.value) > 50:
            raise DomainValidationError("氏名（カナ）は50文字以内で入力してください。")
        if not self.KANA_PATTERN.fullmatch(self.value):
            raise DomainValidationError(
                "氏名（カナ）は全角カタカナで入力してください。"
            )
