"""ASGIアプリケーションの組み立て。

DBエンジンはlifespanでだけ作る。モジュール読み込み時に作ると、``DATABASE_URL``
が無い環境（テスト・OpenAPI生成）で import しただけで落ちる。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.composition import PostgresCompositionRoot
from app.infrastructure.postgres.settings import PostgresSettings
from app.presentational.authentication import (
    ActorContextProvider,
    UnconfiguredActorContextProvider,
)
from app.presentational.dependencies import STATE_ATTRIBUTE, PresentationState
from app.presentational.errors import register_error_handlers
from app.presentational.routers import (
    corporate,
    coverage,
    dispensing,
    medication_history,
    medicine_catalog,
    patient,
    prescription,
    reception,
    staff,
    store,
    system,
)

_TITLE = "PharmacyDomain API"
_VERSION = "0.1.0"


def create_app(*, actor_provider: ActorContextProvider | None = None) -> FastAPI:
    """ルータ・例外翻訳・起動終了処理を結線したアプリケーションを返す。

    Args:
        actor_provider: 資格情報から操作主体を決める認証基盤。省略すると
            すべての業務操作を401で拒否する実装が入る。「未設定なら通す」に
            倒すと、認証基盤を接続し忘れたまま本番へ出た瞬間に全法人の
            データが誰でも読み書きできる。
    """
    provider = (
        actor_provider
        if actor_provider is not None
        else UnconfiguredActorContextProvider()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """起動時にComposition Rootを組み立て、終了時に接続プールを解放する。"""
        root = PostgresCompositionRoot.from_settings(
            PostgresSettings.from_environment()
        )
        setattr(
            app.state,
            STATE_ATTRIBUTE,
            PresentationState(actor_provider=provider, composition_root=root),
        )
        try:
            yield
        finally:
            await root.dispose()

    app = FastAPI(title=_TITLE, version=_VERSION, lifespan=lifespan)
    # 認証基盤はlifespanを待たずに使えるようにする。DB接続を張る前に401を返す。
    setattr(app.state, STATE_ATTRIBUTE, PresentationState(actor_provider=provider))
    register_error_handlers(app)
    for router in (
        system.router,
        corporate.router,
        store.router,
        staff.router,
        patient.router,
        coverage.router,
        reception.router,
        prescription.router,
        dispensing.router,
        medication_history.router,
        medicine_catalog.router,
    ):
        app.include_router(router)
    return app


__all__ = ["create_app"]
