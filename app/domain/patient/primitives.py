"""患者（`patient`）コンテキストの識別子・属性プリミティブ。"""

from app.base.domain.primitives.primitives import BaseDate, EntityUUID


class PatientId(EntityUUID):
    """患者の一意識別子（UUIDv7）。"""

    identifier_name = "患者ID"


class PatientBirthDate(BaseDate):
    """患者の生年月日。"""
