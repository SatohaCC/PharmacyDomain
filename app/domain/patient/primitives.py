"""患者（`patient`）コンテキストの識別子・属性プリミティブ。"""

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseDate,
    BaseNormalizedString,
    BasePositiveInt,
    EntityUUID,
)


class PatientId(EntityUUID):
    """患者の一意識別子（UUIDv7）。"""

    identifier_name = "患者ID"


class PatientExternalIdentifierId(EntityUUID):
    """患者外部識別子の一意識別子（UUIDv7）。"""

    identifier_name = "患者外部識別子ID"


class PatientNumber(BasePositiveInt):
    """法人内で表示・検索に使う患者番号。"""


class ExternalSystemName(BaseNormalizedString):
    """外部患者IDを発行した連携先の名称。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("外部システム名は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError(
                "外部システム名は100文字以内で指定してください。"
            )


class ExternalPatientId(BaseNormalizedString):
    """外部システム側で管理される患者識別子。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("外部患者IDは空にできません。")
        if len(self.value) > 200:
            raise DomainValidationError("外部患者IDは200文字以内で指定してください。")


class PatientBirthDate(BaseDate):
    """患者の生年月日。"""
