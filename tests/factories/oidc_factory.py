"""外部IdPが発行したことにするJWTを、テスト内で作る。

鍵はその場で生成する。JWKSを取りに行かないので、テストはネットワークへ出ない。
落ちた理由が実装の問題なのかネットワークの問題なのかを、切り分けずに済む。
"""

from __future__ import annotations

import hashlib
import hmac
import json
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

#: テストが既定で使う発行元・利用者・主体。
ISSUER = "https://idp.example.test"
AUDIENCE = "pharmacydomain"
SUBJECT = "auth0|000000000000000000000001"


@dataclass(frozen=True, slots=True)
class SigningKeyPair:
    """署名に使う秘密鍵と、検証に使う公開鍵の組。"""

    kid: str
    private_pem: bytes
    public_pem: bytes


@lru_cache(maxsize=8)
def signing_key(kid: str = "test-key") -> SigningKeyPair:
    """``kid`` ごとに鍵を1組だけ作って使い回す。

    RSA鍵の生成は速くないので、ケースごとに作り直すとテスト全体が目に見えて
    遅くなる。鍵の中身はどのケースでも意味を持たないため、使い回してよい。
    """
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return SigningKeyPair(
        kid=kid,
        private_pem=private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        public_pem=private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ),
    )


def issue_token(
    key: SigningKeyPair | None = None,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    subject: str = SUBJECT,
    lifetime: timedelta = timedelta(minutes=5),
    algorithm: str = "RS256",
    signed_with: bytes | str | None = None,
    kid: str | None = None,
    drop: tuple[str, ...] = (),
    extra: dict[str, Any] | None = None,
) -> str:
    """指定した内容のトークンを発行する。

    Args:
        key: 署名鍵。既定の ``kid`` の鍵を使う。
        lifetime: ``exp`` までの長さ。負にすると期限切れのトークンになる。
        signed_with: 署名に使う鍵を差し替える（署名不一致やalg混同を作る）。
        kid: ヘッダへ載せる ``kid``。差し替えると鍵を解決できない状態になる。
        drop: 落とすクレーム名（``sub`` / ``exp`` / ``iss`` / ``aud``）。
    """
    material = signing_key() if key is None else key
    # ``exp`` は PyJWT が実時刻と比べるので、固定時刻では表現できない。
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        **(extra or {}),
    }
    for name in drop:
        payload.pop(name, None)
    if signed_with is not None:
        secret: bytes | str = signed_with
    elif algorithm == "none":
        secret = ""
    else:
        secret = material.private_pem
    return jwt.encode(
        payload,
        secret,
        algorithm=algorithm,
        headers={"kid": material.kid if kid is None else kid},
    )


def forge_confused_algorithm_token(
    key: SigningKeyPair | None = None,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    subject: str = SUBJECT,
) -> str:
    """公開鍵をHMACの鍵として使った ``HS256`` のトークンを手で組む。

    PyJWT の ``encode`` は「非対称鍵をHMACの秘密に使うな」と拒むので、この
    トークンはライブラリ経由では作れない。だが攻撃する側はライブラリを通さない。
    公開鍵は誰でも取得できるので、検証側が ``HS256`` を許していれば、それだけで
    有効なトークンを作れてしまう。実際に手で組んで、**受け取る側**が拒むことを
    確かめる。
    """
    material = signing_key() if key is None else key
    now = datetime.now(UTC)
    header = {"alg": "HS256", "typ": "JWT", "kid": material.kid}
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    signing_input = f"{_encode_segment(header)}.{_encode_segment(payload)}"
    signature = hmac.new(
        material.public_pem, signing_input.encode(), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_base64url(signature)}"


def _encode_segment(value: dict[str, Any]) -> str:
    return _base64url(json.dumps(value, separators=(",", ":")).encode())


def _base64url(raw: bytes) -> str:
    return urlsafe_b64encode(raw).rstrip(b"=").decode()


__all__ = [
    "AUDIENCE",
    "ISSUER",
    "SUBJECT",
    "SigningKeyPair",
    "forge_confused_algorithm_token",
    "issue_token",
    "signing_key",
]
