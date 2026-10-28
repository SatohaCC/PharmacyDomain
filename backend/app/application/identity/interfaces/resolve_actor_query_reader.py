"""操作者の有効性を判断する前に、外部主体に対応する参照事実を取得する契約。"""

from typing import Protocol

from app.application.identity.queries.dtos.identity_resolution import (
    IdentityResolutionSnapshot,
)
from app.domain.identity.primitives import ExternalSubjectKey


class ResolveActorQueryReader(Protocol):
    """認可結果やActorを生成せず、取得した事実だけを返す。"""

    async def get_by_subject(
        self, subject: ExternalSubjectKey
    ) -> IdentityResolutionSnapshot | None:
        """対応アカウントが無ければNone、本人・所属が無ければ欠落した事実を返す。"""
        ...
