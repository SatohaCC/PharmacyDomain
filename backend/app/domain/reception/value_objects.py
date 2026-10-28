"""receptionの複合値と参照スナップショット。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.reception.primitives import (
    ReceptionBillingCode,
    ReceptionBillingName,
    ReceptionBillingPoints,
    ReceptionBillingQuantity,
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionOriginalJson,
)


@dataclass(frozen=True, kw_only=True)
class ReceptionCorrection:
    """レセコン等で修正された処方・受付内容の訂正履歴。"""

    fingerprint: ReceptionFingerprint
    changed_fields: tuple[ReceptionFieldPath, ...]
    received_at: datetime


@dataclass(frozen=True, kw_only=True)
class ReceptionBillingAddition:
    """受付時にレセコン側で算定された調剤報酬の加算項目（調剤基本料加算、地域支援体制加算、時間外加算等）。"""

    code: ReceptionBillingCode
    name: ReceptionBillingName
    points: ReceptionBillingPoints | None = None
    quantity: ReceptionBillingQuantity | None = None


@dataclass(frozen=True, kw_only=True)
class ReceptionSourceData:
    """外部システム（レセコン・NSIPS等）から受信した受付データ原本の控え。"""

    bundle_json: ReceptionOriginalJson
    imported_at: datetime
    is_follow_up: bool = False
    billing_additions: tuple[ReceptionBillingAddition, ...] = ()
