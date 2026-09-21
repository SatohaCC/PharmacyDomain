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
