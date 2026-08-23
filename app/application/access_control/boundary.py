"""他コンテキストが依存する法人アクセス境界の抽象。

Store / Staff / Patient のユースケースは「対象法人の認可と有効状態を確認して法人集約を得る」
ことだけを必要とし、法人コンテキストの実装そのものは必要としません。
利用側がこの Protocol にだけ依存することで、Store / Staff / Patient から
`app.application.corporate` への依存を無くしています（依存関係逆転の原則）。

実装は `app.application.corporate.corporate_access.CorporateAccessService` です。
Protocol と実装のズレは `tests/application/corporate/test_corporate_access.py` の
適合テストと mypy が検出します。
"""

from __future__ import annotations

from typing import Protocol

from app.application.access_control.models import ActorContext, Permission
from app.domain.corporate.corporate import Corporate
from app.domain.corporate.primitives import CorporateId


class CorporateAccessBoundary(Protocol):
    """対象法人の認可・存在・有効状態を確認して法人集約を返す境界。"""

    @property
    def actor(self) -> ActorContext:
        """認可に使用する信頼済み操作主体を返す。"""
        ...

    async def require_active(
        self,
        *,
        corporate_id: CorporateId,
        permission: Permission,
    ) -> Corporate:
        """権限を確認し、有効な対象法人を返す。"""
        ...
