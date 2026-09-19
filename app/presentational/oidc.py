"""外部IdPが発行したJWTを検証して、外部主体を決める本番の認証基盤。

検証に使う鍵の取得は ``SigningKeyResolver`` の向こう側へ置く。JWKSの取得は
ネットワークI/Oなので、ここへ直接書くとテストが実際に外へ出て、落ちた理由が
実装の問題なのかネットワークの問題なのかを切り分けられなくなる。

この窓口が返すのは ``VerifiedSubject``（外部主体）だけである。内部の本人は
``ResolveActorUseCase`` が ``external_subject`` から引く。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import jwt

from app.application.identity.resolve_actor import VerifiedSubject
from app.presentational.authentication import VerifiedSubjectProvider
from app.presentational.exceptions import AuthenticationError

#: 検証に失敗したときの唯一の文言。
#:
#: どのクレームで落ちたかを応答へ出さない。「署名が違う」「発行元が違う」を
#: 区別して返すと、トークンを総当たりする側に一歩ずつ正解を教えることになる。
_FAILURE_MESSAGE = "資格情報を検証できません。"

#: 受け入れてよい署名アルゴリズム。
#:
#: JWKSが配るのは公開鍵なので、共有鍵方式（``HS*``）と ``none`` は受け付けない。
#: 公開鍵をHMACの鍵として使う「アルゴリズムの取り違え」は、``HS256`` を許した
#: 瞬間に成立する（誰でも知っている公開鍵で、有効なトークンを作れてしまう）。
_ALLOWED_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)

#: 必須のクレーム。ひとつでも欠けたトークンは検証済みとして扱わない。
_REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]


class OidcConfigurationError(ValueError):
    """認証基盤の設定が不足または不正な場合の例外。

    未設定は「接続しない」という選択として扱うが、**中途半端な設定は起動を
    止める**。黙って401へ倒すと、設定を間違えた本番が「認証基盤を繋いだのに
    誰も入れない」状態で動き続け、原因が設定ではなく実装に見える。
    """


class SigningKeyResolver(Protocol):
    """トークンのヘッダに対応する検証鍵を返す境界。"""

    async def resolve(self, token: str) -> Any:
        """``kid`` に対応する公開鍵を返す。

        Raises:
            Exception: 鍵を取得できない場合。呼び出し側が認証失敗へ畳む。
        """
        ...


@dataclass(frozen=True, slots=True)
class OidcSettings:
    """JWTの検証に必要な設定。"""

    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway: float = 0.0

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> OidcSettings | None:
        """環境変数から設定を読み込む。

        ``OIDC_ISSUER`` という項目そのものが無ければ ``None`` を返す（接続しない
        という選択）。項目はあるのに空、あるいは他の項目が欠けている場合は、
        設定の誤りとして送出する。
        """
        values = os.environ if environment is None else environment
        if "OIDC_ISSUER" not in values:
            return None
        return cls(
            issuer=_required(values.get("OIDC_ISSUER", ""), "OIDC_ISSUER"),
            audience=_required(values.get("OIDC_AUDIENCE", ""), "OIDC_AUDIENCE"),
            jwks_url=_required(values.get("OIDC_JWKS_URL", ""), "OIDC_JWKS_URL"),
            algorithms=_parse_algorithms(values.get("OIDC_ALGORITHMS")),
            leeway=_parse_leeway(values.get("OIDC_LEEWAY_SECONDS", "")),
        )


class JwksSigningKeyResolver(SigningKeyResolver):
    """JWKSエンドポイントから検証鍵を取得する本番実装。"""

    def __init__(self, jwks_url: str) -> None:
        # ``PyJWKClient`` は生成時に取りに行かない。取得とキャッシュは呼び出し時。
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True)

    async def resolve(self, token: str) -> Any:
        """``kid`` に対応する公開鍵をJWKSから取得する。

        ``PyJWKClient`` は ``urllib`` を使う同期APIなので、そのまま待つとイベント
        ループが止まる。別スレッドへ逃がして、他のリクエストを巻き込まない。
        """
        key = await asyncio.to_thread(self._client.get_signing_key_from_jwt, token)
        return key.key


class OidcVerifiedSubjectProvider(VerifiedSubjectProvider):
    """JWTを検証して外部主体を返す。"""

    def __init__(self, settings: OidcSettings, keys: SigningKeyResolver) -> None:
        self._settings = settings
        self._keys = keys

    async def authenticate(self, credential: str | None) -> VerifiedSubject:
        """トークンを検証し、発行元を含む外部主体を返す。"""
        if not credential:
            raise AuthenticationError(_FAILURE_MESSAGE)
        try:
            key = await self._keys.resolve(credential)
            claims = jwt.decode(
                credential,
                key,
                algorithms=list(self._settings.algorithms),
                issuer=self._settings.issuer,
                audience=self._settings.audience,
                leeway=self._settings.leeway,
                options={"require": _REQUIRED_CLAIMS},
            )
        except Exception as error:
            # 鍵の取得もトークンの検証も、失敗の種類は主体が決まらないという
            # 一点に帰着する。種類ごとに応答を変えず、500へも落とさない。
            raise AuthenticationError(_FAILURE_MESSAGE) from error
        subject = str(claims.get("sub", "")).strip()
        if not subject:
            raise AuthenticationError(_FAILURE_MESSAGE)
        # 発行元を含めた値を主体とする。``sub`` だけにすると、別のIdPを足した日に
        # 両者の ``sub`` が衝突し、他人のアカウントへ当たりうる。
        return VerifiedSubject(principal_id=f"{self._settings.issuer}/{subject}")


def build_verified_subject_provider(
    environment: Mapping[str, str] | None = None,
) -> VerifiedSubjectProvider | None:
    """環境変数から本番の認証基盤を組み立てる。未設定なら ``None``。"""
    settings = OidcSettings.from_environment(environment)
    if settings is None:
        return None
    return OidcVerifiedSubjectProvider(
        settings, JwksSigningKeyResolver(settings.jwks_url)
    )


def _required(raw_value: str, name: str) -> str:
    value = raw_value.strip()
    if not value:
        raise OidcConfigurationError(
            f"{name} が設定されていません。認証基盤を接続するなら、"
            "発行元・利用者・鍵の取得先の3つを揃えてください。"
        )
    return value


def _parse_algorithms(raw_algorithms: str | None) -> tuple[str, ...]:
    """許す署名アルゴリズムを読む。項目が無ければ既定、空なら設定の誤り。

    「空の許可一覧」はどのトークンも検証できない設定であり、既定へ倒す対象では
    ない。項目を書いた以上は値を意図しているはずなので、黙って ``RS256`` へ
    戻さず起動を止める（戻すと、絞ったつもりの設定が効いていないことに気づけない）。
    """
    if raw_algorithms is None:
        return ("RS256",)
    names = tuple(item.strip() for item in raw_algorithms.split(",") if item.strip())
    if not names:
        raise OidcConfigurationError(
            "OIDC_ALGORITHMS が空です。項目を書くなら値を指定してください"
            "（既定の RS256 でよければ項目ごと外します）。"
        )
    unknown = sorted(set(names) - _ALLOWED_ALGORITHMS)
    if unknown:
        allowed = ", ".join(sorted(_ALLOWED_ALGORITHMS))
        raise OidcConfigurationError(
            f"OIDC_ALGORITHMS に受け付けられない値があります: {unknown}。"
            f"公開鍵方式のみ指定できます（{allowed}）。"
        )
    return names


def _parse_leeway(raw_leeway: str) -> float:
    value = raw_leeway.strip()
    if not value:
        return 0.0
    try:
        leeway = float(value)
    except ValueError as error:
        raise OidcConfigurationError(
            f"OIDC_LEEWAY_SECONDS を秒数として読めません: '{value}'。"
        ) from error
    if leeway < 0:
        raise OidcConfigurationError(
            "OIDC_LEEWAY_SECONDS に負の値は指定できません。"
            "期限を前倒しして検証する用途はありません。"
        )
    return leeway


__all__ = [
    "JwksSigningKeyResolver",
    "OidcConfigurationError",
    "OidcSettings",
    "OidcVerifiedSubjectProvider",
    "SigningKeyResolver",
    "build_verified_subject_provider",
]
