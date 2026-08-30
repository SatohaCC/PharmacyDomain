"""開発用の起動点が、開発の外へ漏れないことを固定する。

固定トークン1つで全法人を操作できる起動点なので、危ないのは「設定を間違える」
ことより「本番がこちらを起動する」ことである。設定の検証と、本番イメージの
起動点の両方を検査する。
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application.access_control import ActorRole
from app.presentational import UnconfiguredActorContextProvider, create_app
from app.presentational.dependencies import (
    STATE_ATTRIBUTE,
    PresentationState,
    get_corporate_use_cases,
)
from app.presentational.dev_main import (
    DevActorConfigurationError,
    build_actor_provider,
    create_dev_app,
)
from app.presentational.exceptions import AuthenticationError
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository
from tests.presentational.helpers import create_corporate_use_cases

_ROOT = Path(__file__).resolve().parents[2]
_VENDOR_ENVIRONMENT = {"DEV_ACTOR_TOKEN": "dev-token"}
_CORPORATE_ID = "01890000-0000-7000-8000-000000000000"


async def test_固定トークンと一致したときだけ_主体を返す() -> None:
    # Arrange
    provider = build_actor_provider(_VENDOR_ENVIRONMENT)

    # Act
    actor = await provider.authenticate("dev-token")

    # Assert
    assert actor.roles == frozenset({ActorRole.VENDOR_SYSTEM_ADMIN})
    assert actor.principal_id == "dev-actor"


@pytest.mark.parametrize("credential", [None, "", "another-token"])
async def test_トークンが一致しなければ_認証失敗になる(credential: str | None) -> None:
    # Arrange
    provider = build_actor_provider(_VENDOR_ENVIRONMENT)

    # Act & Assert
    with pytest.raises(AuthenticationError):
        await provider.authenticate(credential)


@pytest.mark.parametrize("token", ["", "   "])
def test_トークン未設定なら_組み立てが失敗する(token: str) -> None:
    """未設定を「何でも通す」に倒すと、開発用の起動点が無条件の穴になる。"""
    # Act & Assert
    with pytest.raises(DevActorConfigurationError, match="DEV_ACTOR_TOKEN"):
        build_actor_provider({"DEV_ACTOR_TOKEN": token})


def test_ASCII以外のトークンは_設定エラーになる() -> None:
    """ヘッダへ載らない値を許すと、起動はできるのに全リクエストが401になる。"""
    # Act & Assert
    with pytest.raises(DevActorConfigurationError, match="ASCII"):
        build_actor_provider({"DEV_ACTOR_TOKEN": "開発用トークン"})


async def test_主体の識別子を_環境変数で指定できる() -> None:
    # Arrange
    provider = build_actor_provider(
        {**_VENDOR_ENVIRONMENT, "DEV_ACTOR_PRINCIPAL_ID": "検証用"}
    )

    # Act
    actor = await provider.authenticate("dev-token")

    # Assert
    assert actor.principal_id == "検証用"


async def test_法人管理者を選ぶと_指定した法人の主体になる() -> None:
    # Arrange
    provider = build_actor_provider(
        {
            **_VENDOR_ENVIRONMENT,
            "DEV_ACTOR_ROLE": "corporate_admin",
            "DEV_ACTOR_CORPORATE_ID": _CORPORATE_ID,
        }
    )

    # Act
    actor = await provider.authenticate("dev-token")

    # Assert
    assert actor.roles == frozenset({ActorRole.CORPORATE_ADMIN})
    assert actor.corporate_id is not None
    assert str(actor.corporate_id.value) == _CORPORATE_ID


def test_法人管理者に法人IDが無いと_設定エラーになる() -> None:
    # Act & Assert
    with pytest.raises(DevActorConfigurationError, match="DEV_ACTOR_CORPORATE_ID"):
        build_actor_provider(
            {**_VENDOR_ENVIRONMENT, "DEV_ACTOR_ROLE": "corporate_admin"}
        )


def test_法人IDの形式が不正なら_設定エラーになる() -> None:
    """ドメインの検証エラーを起動時の設定エラーへ翻訳する。"""
    # Act & Assert
    with pytest.raises(DevActorConfigurationError, match="DEV_ACTOR_CORPORATE_ID"):
        build_actor_provider(
            {
                **_VENDOR_ENVIRONMENT,
                "DEV_ACTOR_ROLE": "corporate_admin",
                "DEV_ACTOR_CORPORATE_ID": "not-a-uuid",
            }
        )


def test_未知のロールは_設定エラーになる() -> None:
    # Act & Assert
    with pytest.raises(DevActorConfigurationError, match="DEV_ACTOR_ROLE"):
        build_actor_provider({**_VENDOR_ENVIRONMENT, "DEV_ACTOR_ROLE": "superuser"})


def test_開発用アプリは_固定トークンで業務ルートを通す(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`/docs` から実際に実行できる状態になっていることを確かめる。"""
    # Arrange
    monkeypatch.setenv("DEV_ACTOR_TOKEN", "dev-token")
    app = create_dev_app()
    app.dependency_overrides[get_corporate_use_cases] = lambda: (
        create_corporate_use_cases(InMemoryCorporateRepository())
    )
    client = TestClient(app)

    # Act
    rejected = client.get(f"/corporates/{_CORPORATE_ID}")
    accepted = client.get(
        f"/corporates/{_CORPORATE_ID}",
        headers={"Authorization": "Bearer dev-token"},
    )

    # Assert: 通った先で「その法人が無い」まで到達する。
    assert rejected.status_code == HTTPStatus.UNAUTHORIZED
    assert accepted.status_code == HTTPStatus.NOT_FOUND
    assert accepted.json()["code"] == "CORPORATE_NOT_FOUND"


def test_開発用アプリは_タイトルで見分けられる(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """開いている `/docs` がどちらの起動点かを画面で判断できるようにする。"""
    # Arrange
    monkeypatch.setenv("DEV_ACTOR_TOKEN", "dev-token")

    # Act
    dev_title = create_dev_app().title

    # Assert
    assert dev_title != create_app().title
    assert "開発用" in dev_title


def test_本番の起動点は_認証を拒否する既定のままである() -> None:
    """`create_app()` の既定が開発用に差し替わっていないことを固定する。"""
    # Act
    state = getattr(create_app().state, STATE_ATTRIBUTE)

    # Assert
    assert isinstance(state, PresentationState)
    assert isinstance(state.actor_provider, UnconfiguredActorContextProvider)


def test_本番イメージの起動点は_開発用ではない() -> None:
    """危ないのは設定間違いより起動点の取り違えなので、そちらを検査する。"""
    # Arrange
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")

    # Act
    command_lines = [
        line
        for line in dockerfile.splitlines()
        if line.startswith(("CMD", "ENTRYPOINT"))
    ]

    # Assert
    assert command_lines, "Dockerfile に起動コマンドが無い"
    assert all("app.main:app" in line for line in command_lines)
    assert all("dev_main" not in line for line in command_lines)


def test_開発用の起動点は_compose_からだけ呼ばれる() -> None:
    """開発用の起動点を指す場所を1つに保つ。"""
    # Arrange
    referring = sorted(
        path.relative_to(_ROOT).as_posix()
        for path in (_ROOT / "compose.yaml", _ROOT / "Dockerfile")
        if "dev_main" in path.read_text(encoding="utf-8")
    )

    # Assert
    assert referring == ["compose.yaml"]
