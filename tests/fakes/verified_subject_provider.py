"""テストで事前に登録された外部主体だけを返す本人確認境界。"""

from app.application.identity.resolve_actor import VerifiedSubject
from app.presentational.authentication import VerifiedSubjectProvider
from app.presentational.exceptions import AuthenticationError


class StubVerifiedSubjectProvider(VerifiedSubjectProvider):
    """HTTP本文を読まず、固定した資格情報と外部主体の対応だけを使う。"""

    def __init__(self, subjects: dict[str, VerifiedSubject]) -> None:
        self._subjects = subjects

    async def authenticate(self, credential: str | None) -> VerifiedSubject:
        """登録済み資格情報の外部主体を返す。"""
        if credential is None or credential not in self._subjects:
            raise AuthenticationError("本人を確認できません。")
        return self._subjects[credential]
