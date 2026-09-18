"""同一トランザクションで成功した集約変更の本人監査。"""

import uuid

from sqlalchemy import insert

from app.application.access_control.models import ActorContext, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.identity.resolve_actor import UnavailableIdentityError
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.schema import operation_audits


async def append_pending_audits(
    work: PostgresUnitOfWork, actor: ActorContext, clock: Clock
) -> None:
    """全保存経路から集めた対象だけを追記する。本文や秘密は保存しない。"""
    if not work.pending_changes:
        return
    if not isinstance(actor, ResolvedActorContext):
        # リクエスト経路では ResolvedActorWriteGuard が保存の時点で弾くので、
        # ここへ来るのは専用のUnit of Workを使う経路だけである。確定直前の
        # 送出は応答後になるため、こちらを唯一の防衛線にしてはならない。
        raise UnavailableIdentityError(
            "更新には本人に結び付いた個人アカウントが必要です。"
        )
    now = clock.now()
    for operation, resource_id, corporate_id, store_id in work.pending_changes:
        await work.session.execute(
            insert(operation_audits).values(
                id=uuid.uuid7(),
                person_id=actor.person_id.value,
                account_id=actor.account_id.value,
                operation=operation,
                resource_id=resource_id,
                corporate_id=corporate_id,
                store_id=store_id,
                recorded_at=now,
            )
        )
    work.pending_changes.clear()
