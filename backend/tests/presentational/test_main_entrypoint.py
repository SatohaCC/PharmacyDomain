"""本番起動点がローカル認証を明示的に有効にすることを検証する。"""

import importlib
from unittest.mock import patch

from app.bootstrap import create_app
from app.presentational.authentication import UnconfiguredActorContextProvider
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState


def test_本番起動点_ローカル認証を明示して組み立てる() -> None:
    # Arrange / Act
    with patch("app.bootstrap.create_app", wraps=create_app) as factory:
        module = importlib.reload(importlib.import_module("app.main"))
        # Assert
        assert factory.call_args.kwargs == {"local_authentication_enabled": True}
        state = getattr(module.app.state, STATE_ATTRIBUTE)
        assert isinstance(state, PresentationState)
        assert isinstance(state.actor_provider, UnconfiguredActorContextProvider)
        assert state.identity_provider is None


def test_本番起動点_外部認証の古い設定を参照しない() -> None:
    # Arrange / Act
    with patch.dict("os.environ", {"OIDC_ISSUER": "未使用の接続先"}):
        module = importlib.reload(importlib.import_module("app.main"))
        # Assert
        state = getattr(module.app.state, STATE_ATTRIBUTE)
        assert isinstance(state, PresentationState)
        assert state.identity_provider is None
