"""Composition Root の網羅性とトランザクション境界のテスト。

Composition Root は「配線を忘れても誰も気づかない」場所である。ユースケースを
足して束へ入れ忘れても、既存のテストは全部通る。だから網羅性そのものを検査する。

トランザクション境界も同じで、コミットの有無は例外にならない。正常終了と異常
終了のそれぞれで、実際にどちらが呼ばれたかを数えて固定する。
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import fields
from typing import Any, get_type_hints

import pytest

import app.application
from app.application.access_control import ActorContext, AuthorizationService
from app.application.access_control.models import ActorRole, ResolvedActorContext
from app.application.composition.clinical_store_guard import ClinicalStoreWriteGuard
from app.application.composition.resolved_actor_guard import (
    CompositeWriteGuard,
    ResolvedActorWriteGuard,
)
from app.application.composition.staff_integrity import StaffAssignmentWriteGuard
from app.application.identity.resolve_actor import UnavailableIdentityError
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.infrastructure.di import (
    PostgresRequestScope,
    PostgresUseCaseRegistry,
)
from tests.fakes.fake_clock import FakeClock
from tests.fakes.recording_async_session import RecordingAsyncSession
from tests.infrastructure.postgres.helpers import create_corporate, create_unit_of_work

_APPLICATION_PACKAGE = "app.application."


def _qualified(klass: type[object]) -> str:
    """クラスを「モジュール.クラス名」で表す。"""
    return f"{klass.__module__}.{klass.__qualname__}"


def _declared_use_cases() -> dict[str, type[object]]:
    """``app/application`` に定義された全ユースケースを集める。"""
    declared: dict[str, type[object]] = {}
    for module_info in pkgutil.walk_packages(
        app.application.__path__, _APPLICATION_PACKAGE
    ):
        module = importlib.import_module(module_info.name)
        for name, value in vars(module).items():
            if not isinstance(value, type) or not name.endswith("UseCase"):
                continue
            # 再エクスポートを二重に数えない。定義元のモジュールでだけ拾う。
            if value.__module__ != module_info.name:
                continue
            declared[_qualified(value)] = value
    return declared


def _wired_use_cases() -> dict[str, type[object]]:
    """Composition Root の束に配線されたユースケースを集める。"""
    wired: dict[str, type[object]] = {}
    for bundle in get_type_hints(PostgresUseCaseRegistry).values():
        for use_case in get_type_hints(bundle).values():
            wired[_qualified(use_case)] = use_case
    return wired


def _build_scope(session: RecordingAsyncSession) -> PostgresRequestScope:
    """記録用セッションの上に本番と同じ構成のスコープを組み立てる。"""
    return PostgresRequestScope(
        create_unit_of_work(session),
        authorization=AuthorizationService(
            ActorContext.vendor_system_admin(principal_id="composition-test")
        ),
        clock=FakeClock(),
    )


def test_全ユースケースがComposition_Rootに配線されている() -> None:
    """束へ入れ忘れたユースケースは PostgreSQL 経路から実行できない。"""
    # Arrange & Act
    declared = _declared_use_cases()
    wired = _wired_use_cases()

    # Assert
    assert set(declared) == set(wired), (
        f"未配線: {sorted(set(declared) - set(wired))} / "
        f"実体の無い配線: {sorted(set(wired) - set(declared))}"
    )


def test_配線されたユースケースは_宣言どおりの型で組み立てられる() -> None:
    """引数の並び違いや取り違えを、実際に組み立てて確かめる。"""
    # Arrange
    scope = _build_scope(RecordingAsyncSession())

    # Act
    registry = scope.use_cases

    # Assert
    for bundle_name in get_type_hints(PostgresUseCaseRegistry):
        bundle = getattr(registry, bundle_name)
        hints = get_type_hints(type(bundle))
        for use_case_field in fields(bundle):
            use_case = getattr(bundle, use_case_field.name)
            expected = hints[use_case_field.name]
            assert isinstance(use_case, expected), (
                f"{bundle_name}.{use_case_field.name} が {expected} ではない。"
            )


async def test_スコープの外でユースケースを実行すると_実行時エラーになる() -> None:
    """トランザクションを開かずに保存できる経路が無いことを固定する。

    「境界を張り忘れたまま書き込みが成功する」ことが起きないのは、規約ではなく
    ``PostgresUnitOfWork`` がコンテキスト外でセッションを渡さないからである。
    """
    # Arrange
    scope = _build_scope(RecordingAsyncSession())

    # Act & Assert
    with pytest.raises(RuntimeError):
        await scope.use_cases.corporate.get.execute(
            "01890000-0000-7000-8000-000000000000"
        )


async def test_スコープが正常終了すると_コミットされる() -> None:
    """コミットを呼び出し側の作法に委ねない。"""
    # Arrange
    session = RecordingAsyncSession()
    scope = _build_scope(session)

    # Act
    async with scope:
        pass

    # Assert
    assert session.commits == 1
    assert session.closed == 1


async def test_スコープが例外で終わると_コミットされない() -> None:
    """途中で失敗した書き込みが確定しないことを固定する。"""
    # Arrange
    session = RecordingAsyncSession()
    scope = _build_scope(session)

    # Act
    with pytest.raises(ValueError):
        async with scope:
            raise ValueError("ユースケースの失敗")

    # Assert
    assert session.commits == 0
    assert session.rollbacks == 1
    assert session.closed == 1


async def test_コミットに失敗しても_セッションは閉じられる() -> None:
    """接続がプールへ返らないと、失敗が積み上がったときに枯れる。"""

    # Arrange
    class FailingCommitSession(RecordingAsyncSession):
        """コミットだけが失敗するセッション。"""

        async def commit(self) -> None:
            """確定を試みて必ず失敗する。"""
            await super().commit()
            raise RuntimeError("コミットに失敗しました")

    session = FailingCommitSession()
    scope = _build_scope(session)

    # Act
    with pytest.raises(RuntimeError):
        async with scope:
            pass

    # Assert
    assert session.closed == 1


def test_Repository一式が同じUnit_of_Workを共有する() -> None:
    """世代の追跡が分裂すると、楽観ロックが当たらなくなる。"""
    # Arrange
    scope = _build_scope(RecordingAsyncSession())

    # Act
    repositories = scope.repositories
    shared: set[int] = {
        id(getattr(repositories, item.name)._unit_of_work)
        for item in fields(repositories)
    }

    # Assert
    assert len(shared) == 1


def test_ユースケース束の一覧が_登録簿の項目と一致する() -> None:
    """束を作っても登録簿へ足し忘れると、そのコンテキストは実行できない。"""
    # Arrange
    registry_bundles = set(get_type_hints(PostgresUseCaseRegistry).values())

    # Act
    module = importlib.import_module("app.infrastructure.di")
    exported: set[Any] = {
        getattr(module, name)
        for name in module.__all__
        if name.endswith("UseCases") and isinstance(getattr(module, name), type)
    }

    # Assert
    assert exported == registry_bundles


# --------------------------------------------------------------------------
# 本人未特定の更新
# --------------------------------------------------------------------------


def _resolved_actor() -> ResolvedActorContext:
    """本人とアカウントを特定済みのベンダー管理者。"""
    return ResolvedActorContext(
        principal_id="composition-test",
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        roles=frozenset({ActorRole.VENDOR_SYSTEM_ADMIN}),
    )


async def test_本人未特定の保存は_確定前に拒否される() -> None:
    """判定を確定直前へ置くと、応答送信後の例外になりロールバックが見えない。

    FastAPI の yield 依存は ``yield`` 以降を応答後に実行するので、確定直前で
    弾く設計では、クライアントが 201 と採番されたIDを受け取ったあとに黙って
    取り消される。保存そのものを止めれば、例外はハンドラ実行中に出る。
    """
    # Arrange
    session = RecordingAsyncSession()
    scope = _build_scope(session)

    # Act & Assert
    with pytest.raises(UnavailableIdentityError):
        async with scope:
            await scope.repositories.corporate.save(create_corporate())

    # 行を書く文まで到達していない。確定もされない。
    assert session.executed == []
    assert session.commits == 0
    assert session.rollbacks == 1


async def test_本人特定済みの保存は_そのまま行へ到達する() -> None:
    """拒否が本人特定の有無だけに依存していることを確かめる。"""
    # Arrange
    session = RecordingAsyncSession()
    scope = PostgresRequestScope(
        create_unit_of_work(session),
        authorization=AuthorizationService(_resolved_actor()),
        clock=FakeClock(),
    )

    # Act
    async with scope:
        await scope.repositories.corporate.save(create_corporate())

    # Assert
    assert session.executed, "保存の文が発行されていない"
    assert session.commits == 1


def test_保存前の境界が_宣言した順で全て掛かる() -> None:
    """境界を配線から落としても、DBなしのテストでは気づけない。

    本人特定・臨床集約の店舗状態・スタッフと任命の整合は、どれも「保存の手前で
    止める」ことで全経路に掛かる。1つ外すと、その検査だけが静かに無くなる。
    """
    # Arrange
    session = RecordingAsyncSession()
    work = create_unit_of_work(session)

    # Act
    PostgresRequestScope(
        work,
        authorization=AuthorizationService(_resolved_actor()),
        clock=FakeClock(),
    )

    # Assert
    guard = work.before_save
    assert guard is not None
    owner = getattr(guard, "__self__", None)
    assert isinstance(owner, CompositeWriteGuard)
    applied = [type(getattr(item, "__self__", None)) for item in owner.guards]
    assert applied == [
        ResolvedActorWriteGuard,
        ClinicalStoreWriteGuard,
        StaffAssignmentWriteGuard,
    ]
