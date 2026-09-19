"""外部IdPのトークンを検証する認証基盤。

鍵はテスト内で生成し、JWKSを取りに行かない。確かめるのは署名アルゴリズムの
正しさ（PyJWTの責務）ではなく、**このアプリの使い方**である —— 許す
アルゴリズムを明示しているか、`iss` / `aud` / `exp` / `sub` を必須にしているか、
失敗を全部401へ畳んでいるか。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta
from functools import partial
from pathlib import Path

import pytest

from app.presentational.exceptions import AuthenticationError
from app.presentational.oidc import (
    OidcConfigurationError,
    OidcSettings,
    OidcVerifiedSubjectProvider,
    build_verified_subject_provider,
)
from tests.factories.oidc_factory import (
    AUDIENCE,
    ISSUER,
    SUBJECT,
    forge_confused_algorithm_token,
    issue_token,
    signing_key,
)
from tests.fakes.signing_key_resolver import StubSigningKeyResolver

_ROOT = Path(__file__).resolve().parents[2]
_JWKS_URL = "https://idp.example.test/.well-known/jwks.json"

_VALID_ENVIRONMENT = {
    "OIDC_ISSUER": ISSUER,
    "OIDC_AUDIENCE": AUDIENCE,
    "OIDC_JWKS_URL": _JWKS_URL,
}

#: 検証を通してはならないトークンの作り方。ラベルがケースIDの代わりになる。
#:
#: ``alg混同`` だけ手組みなのは、PyJWT の ``encode`` が「非対称鍵をHMACの秘密に
#: 使うな」と拒むからである。攻撃する側はライブラリを通さないので、作れないことを
#: 「起きない」と読み替えない。
_REJECTED_TOKENS: dict[str, Callable[[], str]] = {
    "署名不一致": partial(issue_token, signed_with=signing_key("別の鍵").private_pem),
    "期限切れ": partial(issue_token, lifetime=timedelta(minutes=-5)),
    "iss不一致": partial(issue_token, issuer="https://evil.example.test"),
    "aud不一致": partial(issue_token, audience="別のアプリ"),
    "alg_none": partial(issue_token, algorithm="none"),
    "alg混同": forge_confused_algorithm_token,
    "未知のkid": partial(issue_token, kid="身に覚えのない鍵"),
    "sub欠落": partial(issue_token, drop=("sub",)),
    "exp欠落": partial(issue_token, drop=("exp",)),
    "iss欠落": partial(issue_token, drop=("iss",)),
    "aud欠落": partial(issue_token, drop=("aud",)),
}
_REJECTED_CREDENTIALS = {
    "壊れた文字列": "not.a.token",
    "空文字": "",
    "ヘッダ無し": None,
}


def _settings(**overrides: object) -> OidcSettings:
    values: dict[str, object] = {
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_url": _JWKS_URL,
        **overrides,
    }
    return OidcSettings(**values)  # type: ignore[arg-type]


def _provider(
    *, keys: StubSigningKeyResolver | None = None, **overrides: object
) -> tuple[OidcVerifiedSubjectProvider, StubSigningKeyResolver]:
    resolver = StubSigningKeyResolver(signing_key()) if keys is None else keys
    return OidcVerifiedSubjectProvider(_settings(**overrides), resolver), resolver


# ---------------------------------------------------------------------------
# トークンの検証
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_正しいトークンは検証済みの外部主体になる() -> None:
    # Arrange
    provider, _ = _provider()

    # Act
    subject = await provider.authenticate(issue_token())

    # Assert
    assert subject.principal_id


@pytest.mark.asyncio
async def test_外部主体は発行元を含む() -> None:
    """``sub`` だけを主体にしない。

    別のIdPを足した日に、両者の ``sub`` が同じ値を返すと主体が衝突する。発行元を
    含めておけば、その日に既存のアカウントを作り直さずに済む。
    """
    # Arrange
    provider, _ = _provider()

    # Act
    subject = await provider.authenticate(issue_token())

    # Assert
    assert subject.principal_id == f"{ISSUER}/{SUBJECT}"


@pytest.mark.asyncio
@pytest.mark.parametrize("label", sorted(_REJECTED_TOKENS))
async def test_検証できないトークンは全て認証失敗になる(label: str) -> None:
    # Arrange
    provider, _ = _provider()

    # Act & Assert
    with pytest.raises(AuthenticationError):
        await provider.authenticate(_REJECTED_TOKENS[label]())


@pytest.mark.asyncio
@pytest.mark.parametrize("label", sorted(_REJECTED_CREDENTIALS))
async def test_トークンの形をしていない資格情報も認証失敗になる(label: str) -> None:
    # Arrange
    provider, _ = _provider()

    # Act & Assert
    with pytest.raises(AuthenticationError):
        await provider.authenticate(_REJECTED_CREDENTIALS[label])


@pytest.mark.asyncio
async def test_失敗の理由は応答に出さない() -> None:
    """どのクレームで落ちたかは、トークンを総当たりする側への手掛かりになる。"""
    # Arrange
    provider, _ = _provider()
    messages: set[str] = set()

    # Act
    for build in _REJECTED_TOKENS.values():
        with pytest.raises(AuthenticationError) as caught:
            await provider.authenticate(build())
        messages.add(caught.value.message)
    for credential in _REJECTED_CREDENTIALS.values():
        with pytest.raises(AuthenticationError) as caught:
            await provider.authenticate(credential)
        messages.add(caught.value.message)

    # Assert
    assert len(messages) == 1, f"失敗の内訳が応答に出ている: {sorted(messages)}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("leeway", "accepted"), [(30.0, True), (0.0, False)])
async def test_許容する時刻のずれは設定で決まる(leeway: float, accepted: bool) -> None:
    # Arrange: 5秒前に期限切れになったトークン。
    provider, _ = _provider(leeway=leeway)
    token = issue_token(lifetime=timedelta(seconds=-5))

    # Act & Assert
    if accepted:
        assert await provider.authenticate(token)
    else:
        with pytest.raises(AuthenticationError):
            await provider.authenticate(token)


@pytest.mark.asyncio
async def test_鍵を取得できないときも認証失敗として返す() -> None:
    """JWKSが引けない状態を500にしない。主体が決まらないことは401である。"""
    # Arrange
    provider, _ = _provider(
        keys=StubSigningKeyResolver(failure=RuntimeError("JWKSへ到達できない"))
    )

    # Act & Assert
    with pytest.raises(AuthenticationError):
        await provider.authenticate(issue_token())


@pytest.mark.asyncio
async def test_鍵の取得は境界の向こう側で一度だけ行う() -> None:
    """検証1回につき鍵の解決も1回。毎回JWKSを取りに行く形にしない。"""
    # Arrange
    provider, resolver = _provider()

    # Act
    await provider.authenticate(issue_token())

    # Assert
    assert resolver.calls == 1


# ---------------------------------------------------------------------------
# 設定の読み取り
# ---------------------------------------------------------------------------


def test_環境変数から設定を読み込む() -> None:
    # Act
    settings = OidcSettings.from_environment(_VALID_ENVIRONMENT)

    # Assert
    assert settings is not None
    assert settings.issuer == ISSUER
    assert settings.audience == AUDIENCE
    assert settings.jwks_url == _JWKS_URL
    assert settings.algorithms == ("RS256",)
    assert settings.leeway == 0.0


def test_許すアルゴリズムは複数指定できる() -> None:
    # Act
    settings = OidcSettings.from_environment(
        {**_VALID_ENVIRONMENT, "OIDC_ALGORITHMS": "RS256, RS512"}
    )

    # Assert
    assert settings is not None
    assert settings.algorithms == ("RS256", "RS512")


def test_発行元が未設定なら認証基盤を接続しない() -> None:
    """未設定は「繋がない」という選択。既定の401のまま起動する。"""
    # Act
    settings = OidcSettings.from_environment(
        {"OIDC_AUDIENCE": AUDIENCE, "OIDC_JWKS_URL": _JWKS_URL}
    )

    # Assert
    assert settings is None
    assert build_verified_subject_provider({}) is None


def test_設定が揃っていれば認証基盤を組み立てる() -> None:
    # Act
    provider = build_verified_subject_provider(_VALID_ENVIRONMENT)

    # Assert
    assert isinstance(provider, OidcVerifiedSubjectProvider)


@pytest.mark.parametrize(
    ("label", "environment"),
    [
        ("audience欠落", {"OIDC_ISSUER": ISSUER, "OIDC_JWKS_URL": _JWKS_URL}),
        ("jwks_url欠落", {"OIDC_ISSUER": ISSUER, "OIDC_AUDIENCE": AUDIENCE}),
        ("issuer空白", {**_VALID_ENVIRONMENT, "OIDC_ISSUER": "   "}),
        ("algorithms空", {**_VALID_ENVIRONMENT, "OIDC_ALGORITHMS": ""}),
        ("algorithms区切りのみ", {**_VALID_ENVIRONMENT, "OIDC_ALGORITHMS": ","}),
        (
            "algorithms未知",
            {**_VALID_ENVIRONMENT, "OIDC_ALGORITHMS": "RS256, 独自方式"},
        ),
        ("algorithmsにnone", {**_VALID_ENVIRONMENT, "OIDC_ALGORITHMS": "none"}),
        ("leeway非数値", {**_VALID_ENVIRONMENT, "OIDC_LEEWAY_SECONDS": "すぐ"}),
        ("leeway負", {**_VALID_ENVIRONMENT, "OIDC_LEEWAY_SECONDS": "-1"}),
    ],
)
def test_設定が不完全なら起動を止める(label: str, environment: dict[str, str]) -> None:
    """黙って401へ倒すと、設定の誤りが実装の不具合に見える。"""
    # Act & Assert
    with pytest.raises(OidcConfigurationError):
        build_verified_subject_provider(environment)


def test_本番の起動点が読む変数は_env_exampleに載っている() -> None:
    """設定する側が、何を埋めればよいか一覧から分かる状態を保つ。

    一覧を手で持つと、変数を足したときに一覧だけが古くなる。読む側の本文から
    引くので、``values.get`` を書いた時点で検査の対象に入る。
    """
    # Arrange
    source = (_ROOT / "app" / "presentational" / "oidc.py").read_text(encoding="utf-8")
    example = (_ROOT / ".env.example").read_text(encoding="utf-8")

    # Act
    names = set(re.findall(r'values\.get\(\s*"(OIDC_[A-Z_]+)"', source))
    missing = sorted(name for name in names if f"{name}=" not in example)

    # Assert
    assert names, "oidc.py が OIDC_* を読んでいない"
    assert missing == [], f".env.example に無い変数: {missing}"
