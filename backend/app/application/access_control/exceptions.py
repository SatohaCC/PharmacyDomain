"""認可・境界検証固有のアプリケーション例外。"""

from app.application.common.exceptions import NotFoundError


class TenantBoundaryNotFoundError(NotFoundError):
    """別法人の存在を漏らさないために返す404相当の例外。

    Note:
        通常のリソース未検出（NotFoundError）とクライアント側で完全に同一に
        見せる必要があるため、既定メッセージとエラーコードを親クラスと意図的に
        同一値としています。
    """

    default_message = "指定されたリソースが見つかりません。"
    default_code = "RESOURCE_NOT_FOUND"
