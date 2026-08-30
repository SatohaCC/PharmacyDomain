"""調剤完了のトランザクション境界を、実PostgreSQLと本番の組み立てで検証する。

調剤セッションの保存と処方箋の状態更新は別々の集約であり、片方だけが残ると
「調剤済の処方箋に調剤の記録が無い」「調剤したのに処方箋が未調剤のまま」という
どちらも復旧に人手が要る状態になる。1トランザクションに入っていることは、
実際に途中で失敗させてみるまで確かめられない。

組み立てには本番の Composition Root をそのまま使う。テスト専用の配線で通しても、
本番の配線が同じである保証にならない。トランザクション境界は
``PostgresRequestScope`` が握っており、ユースケースは境界を知らない。
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.access_control import ActorContext, AuthorizationService
from app.application.dispensing.complete_dispensing import CompleteDispensingCommand
from app.application.dispensing.exceptions import (
    DispensingPrescriptionNotFoundError,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import (
    DispensingCompletionType,
    DispensingProcessStatus,
)
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import PrescriptionStatus
from app.infrastructure.composition import PostgresCompositionRoot
from app.infrastructure.postgres.repositories.dispensing import (
    PostgresDispensingProcessRepository,
)
from app.infrastructure.postgres.repositories.prescription import (
    PostgresPrescriptionRepository,
)
from app.infrastructure.postgres.settings import PostgresSettings
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from tests.factories.dispensing_factory import create_dispensing, verify_passed
from tests.factories.prescription_factory import create_prescription
from tests.infrastructure.postgres.helpers import create_corporate


def _authorization() -> AuthorizationService:
    """全法人を操作できるベンダーシステム管理者。"""
    return AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="integration-vendor-admin")
    )


async def _save_corporate_and_dispensing(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    with_prescription: bool,
) -> tuple[CorporateId, Prescription, DispensingProcess]:
    """法人・処方箋・最終鑑査済の調剤セッションを用意する。

    ``with_prescription`` を ``False`` にすると、調剤完了時に処方箋の更新だけが
    失敗する状態を作れる。
    """
    corporate = create_corporate("調剤完了トランザクション薬局")
    # 受付済のままでは調剤済へ遷移できない。実運用でも調剤開始前に確定させる。
    prescription = create_prescription(corporate_id=corporate.id).ready_for_dispensing()
    process = verify_passed(
        create_dispensing(
            corporate_id=corporate.id,
            prescription_id=prescription.id,
        )
    )

    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        from app.infrastructure.postgres.repositories.corporate import (
            PostgresCorporateRepository,
        )

        await PostgresCorporateRepository(unit_of_work).save(corporate)
        if with_prescription:
            await PostgresPrescriptionRepository(unit_of_work).save(prescription)
        await PostgresDispensingProcessRepository(unit_of_work).save(process)
        await unit_of_work.commit()

    return corporate.id, prescription, process


async def test_調剤完了が_調剤と処方箋を同じトランザクションで確定する(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    postgres_settings: PostgresSettings,
) -> None:
    """終了区分なら、調剤セッションの完了と処方箋の調剤済が両方残る。"""
    # Arrange
    corporate_id, prescription, process = await _save_corporate_and_dispensing(
        session_factory, with_prescription=True
    )
    root = PostgresCompositionRoot.from_settings(postgres_settings)

    # Act
    try:
        async with root.request_scope(authorization=_authorization()) as scope:
            await scope.use_cases.dispensing.complete.execute(
                CompleteDispensingCommand(
                    corporate_id=str(corporate_id.value),
                    dispensing_id=str(process.id.value),
                    completion_type=DispensingCompletionType.COMPLETED.value,
                )
            )
    finally:
        await root.dispose()

    # Assert
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        stored_process = await PostgresDispensingProcessRepository(reader).get(
            corporate_id=corporate_id, dispensing_id=process.id
        )
        stored_prescription = await PostgresPrescriptionRepository(reader).get(
            corporate_id=corporate_id, prescription_id=prescription.id
        )

    assert stored_process is not None
    assert stored_process.status is DispensingProcessStatus.COMPLETED
    assert stored_prescription is not None
    assert stored_prescription.status is PrescriptionStatus.DISPENSED

    del engine


async def test_処方箋の更新に失敗すると_調剤の保存も巻き戻る(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    postgres_settings: PostgresSettings,
) -> None:
    """順序で妥協していた頃は、調剤だけが完了して処方箋が取り残された。"""
    # Arrange: 処方箋を保存しないので、調剤の保存の後に必ず失敗する
    corporate_id, _, process = await _save_corporate_and_dispensing(
        session_factory, with_prescription=False
    )
    root = PostgresCompositionRoot.from_settings(postgres_settings)

    # Act
    try:
        with pytest.raises(DispensingPrescriptionNotFoundError):
            async with root.request_scope(authorization=_authorization()) as scope:
                await scope.use_cases.dispensing.complete.execute(
                    CompleteDispensingCommand(
                        corporate_id=str(corporate_id.value),
                        dispensing_id=str(process.id.value),
                        completion_type=DispensingCompletionType.COMPLETED.value,
                    )
                )
    finally:
        await root.dispose()

    # Assert: 調剤セッションは完了前の状態のまま残っている
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        stored_process = await PostgresDispensingProcessRepository(reader).get(
            corporate_id=corporate_id, dispensing_id=process.id
        )

    assert stored_process is not None
    assert stored_process.status is DispensingProcessStatus.VERIFIED

    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT version FROM dispensing_processes WHERE id = :id"),
            {"id": process.id.value},
        )
        assert int(result.scalar_one()) == 1, "巻き戻ったのに世代が進んでいる。"


async def test_継続区分なら_処方箋は調剤済にならない(
    engine: AsyncEngine,
    session_factory: async_sessionmaker[AsyncSession],
    postgres_settings: PostgresSettings,
) -> None:
    """リフィル・分割の途中で処方箋を閉じると、残りの回が調剤できなくなる。"""
    # Arrange
    corporate_id, prescription, process = await _save_corporate_and_dispensing(
        session_factory, with_prescription=True
    )
    root = PostgresCompositionRoot.from_settings(postgres_settings)

    # Act
    try:
        async with root.request_scope(authorization=_authorization()) as scope:
            await scope.use_cases.dispensing.complete.execute(
                CompleteDispensingCommand(
                    corporate_id=str(corporate_id.value),
                    dispensing_id=str(process.id.value),
                    completion_type=DispensingCompletionType.CONTINUES.value,
                    next_dispensing_date=date(2026, 9, 21),
                )
            )
    finally:
        await root.dispose()

    # Assert
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        stored_prescription = await PostgresPrescriptionRepository(reader).get(
            corporate_id=corporate_id, prescription_id=prescription.id
        )

    assert stored_prescription is not None
    assert stored_prescription.status is not PrescriptionStatus.DISPENSED

    del engine
