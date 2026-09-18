"""テストで事前に登録された本人だけを返す認証境界。"""

from app.application.identity.resolve_actor import VerifiedIdentity
from app.presentational.authentication import VerifiedIdentityProvider
from app.presentational.exceptions import AuthenticationError


class StubVerifiedIdentityProvider(VerifiedIdentityProvider):
    """HTTP本文を読まず、固定した資格情報と本人の対応だけを使う。"""

    def __init__(self, identities: dict[str, VerifiedIdentity]) -> None:
        self._identities = identities

    async def authenticate(self, credential: str | None) -> VerifiedIdentity:
        """登録済み資格情報の本人を返す。"""
        if credential is None or credential not in self._identities:
            raise AuthenticationError("本人を確認できません。")
        return self._identities[credential]
