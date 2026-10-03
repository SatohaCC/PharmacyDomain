"""NSIPS連携の例外定義。"""

from __future__ import annotations

from app.application.common.exceptions import ApplicationError


class NsipsError(ApplicationError):
    """NSIPS連携関連の基底例外。"""

    default_message = "NSIPS連携エラーが発生しました。"
    default_code = "NSIPS_ERROR"


class NsipsParseError(NsipsError):
    """NSIPSデータの構文解析に失敗した場合の例外。"""

    default_message = "NSIPSデータの構文解析に失敗しました。"
    default_code = "NSIPS_PARSE_ERROR"


class NsipsIngestionError(NsipsError):
    """NSIPSデータの取込処理に失敗した場合の例外。"""

    default_message = "NSIPSデータの取込処理に失敗しました。"
    default_code = "NSIPS_INGESTION_ERROR"


class NsipsPatientIdentityConflictError(NsipsError):
    """受付と受信データの患者同一性を確認できない場合の例外。"""

    default_message = "患者の同一性を確認し、照合済みの患者IDで再送してください。"
    default_code = "NSIPS_PATIENT_IDENTITY_CONFLICT"
