"""登録済みの鍵だけを返す検証鍵の境界。"""

from typing import Any

import jwt

from app.presentational.oidc import SigningKeyResolver
from tests.factories.oidc_factory import SigningKeyPair


class UnknownSigningKeyError(LookupError):
    """``kid`` に対応する鍵が無い。本番のJWKS取得失敗に対応する。"""


class StubSigningKeyResolver(SigningKeyResolver):
    """``kid`` で引ける鍵だけを返し、引けなければ送出する。

    本番実装はJWKSを取りに行くが、ここは取りに行かない。鍵の取り違えと取得
    失敗の2つだけを再現すれば、呼び出し側の振る舞いは固定できる。
    """

    def __init__(self, *keys: SigningKeyPair, failure: Exception | None = None) -> None:
        self._keys = {key.kid: key.public_pem for key in keys}
        self._failure = failure
        #: 解決を試みた回数。境界の向こう側が何度呼ばれたかを観測する。
        self.calls = 0

    async def resolve(self, token: str) -> Any:
        """トークンのヘッダの ``kid`` に対応する公開鍵を返す。"""
        self.calls += 1
        if self._failure is not None:
            raise self._failure
        kid = jwt.get_unverified_header(token).get("kid")
        if kid not in self._keys:
            raise UnknownSigningKeyError(f"鍵が見つかりません: {kid}")
        return self._keys[kid]
