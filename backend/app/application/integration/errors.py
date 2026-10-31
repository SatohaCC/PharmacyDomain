"""Applicationのerrorsを定義する。"""

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


class NsipsSourceConflictError(NsipsError):
    """NSIPS原本の期待ハッシュ値が不一致または不足している場合の例外。"""

    default_message = (
        "NSIPS原本の競合が発生しました。最新の原本情報を確認してください。"
    )
    default_code = "NSIPS_SOURCE_CONFLICT"


class NsipsReceptionNotFoundError(NsipsError):
    """訂正または削除対象の受付が見つからない場合の例外。"""

    default_message = "対象の受付が見つかりません。"
    default_code = "NSIPS_RECEPTION_NOT_FOUND"
