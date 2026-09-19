"""本番の起動点が、設定に応じて認証基盤を差し込む（あるいは差し込まない）。

危ないのは「繋いだつもりで繋がっていない」状態と、「設定を間違えたまま動き
続ける」状態の2つである。前者は既定の401で、後者は起動時の失敗で止める。
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator

import pytest

from app.presentational import UnconfiguredActorContextProvider
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from app.presentational.oidc import OidcConfigurationError, OidcVerifiedSubjectProvider
from tests.factories.oidc_factory import AUDIENCE, ISSUER

_VARIABLES = (
    "OIDC_ISSUER",
    "OIDC_AUDIENCE",
    "OIDC_JWKS_URL",
    "OIDC_ALGORITHMS",
    "OIDC_LEEWAY_SECONDS",
)
_JWKS_URL = "https://idp.example.test/.well-known/jwks.json"


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """``OIDC_*`` を外した状態から始め、終わったら起動点を元へ戻す。"""
    for name in _VARIABLES:
        monkeypatch.delenv(name, raising=False)
    yield
    for name in _VARIABLES:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(importlib.import_module("app.main"))


def _state() -> PresentationState:
    module = importlib.reload(importlib.import_module("app.main"))
    state = getattr(module.app.state, STATE_ATTRIBUTE)
    assert isinstance(state, PresentationState)
    return state


def test_認証基盤が未設定なら業務操作を拒否する既定のまま起動する(
    clean_environment: None,
) -> None:
    # Act
    state = _state()

    # Assert
    assert state.identity_provider is None
    assert isinstance(state.actor_provider, UnconfiguredActorContextProvider)


def test_設定が揃っていれば外部IdPを接続して起動する(
    clean_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arrange
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("OIDC_JWKS_URL", _JWKS_URL)

    # Act
    state = _state()

    # Assert
    assert isinstance(state.identity_provider, OidcVerifiedSubjectProvider)


def test_設定が中途半端なら起動しない(
    clean_environment: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """黙って401へ倒すと、繋いだつもりの本番が誰も入れないまま動き続ける。"""
    # Arrange
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)

    # Act & Assert
    with pytest.raises(OidcConfigurationError):
        _state()
