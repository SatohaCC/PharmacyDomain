"""実PostgreSQLに対する永続化の振る舞いを検証する。

DBなしのテストで固定できるのは「どんなSQLを組み立てたか」までで、``ON CONFLICT``
が何行に当たるか、asyncpg が制約名をどう返すか、部分一意インデックスがどの行を
弾くかはサーバが決める。ここが実挙動の唯一の確認点になる。
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.corporate.corporate import Corporate
from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.foundation.exceptions import ConcurrentModificationError
from app.domain.patient.primitives import PatientId
from app.domain.prescription.exceptions import (
    PrescriptionDocumentNumberAlreadyExistsError,
)
from app.domain.prescription.primitives import (
    PrescriptionDocumentNumber,
    PrescriptionSourceType,
)
from app.infrastructure.postgres.repositories.corporate import (
    PostgresCorporateRepository,
)
from app.infrastructure.postgres.repositories.dispensing import (
    PostgresDispensingProcessRepository,
)
from app.infrastructure.postgres.repositories.prescription import (
    PostgresPrescriptionRepository,
)
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.prescription_factory import create_prescription
from tests.infrastructure.postgres.helpers import create_corporate


async def _stored_version(engine: AsyncEngine, corporate: Corporate) -> int:
    """DBに入っている世代を直接読む。"""
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT version FROM corporates WHERE id = :id"),
            {"id": corporate.id.value},
        )
        return int(result.scalar_one())


async def _count(engine: AsyncEngine, table_name: str) -> int:
    """テーブルの行数を直接読む。"""
    async with engine.connect() as connection:
        result = await connection.execute(text(f"SELECT count(*) FROM {table_name}"))
        return int(result.scalar_one())


# --------------------------------------------------------------------------
# 保存と復元
# --------------------------------------------------------------------------


async def test_保存した法人が_同じ内容で復元できる(
    unit_of_work: PostgresUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """payloadを正として、別トランザクションからも同じ集約が読める。"""
    # Arrange
    corporate = create_corporate("結合テスト薬局")

    # Act
    async with unit_of_work:
        await PostgresCorporateRepository(unit_of_work).save(corporate)
        await unit_of_work.commit()

    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        restored = await PostgresCorporateRepository(reader).get(corporate.id)

    # Assert
    assert restored is not None
    assert restored.id == corporate.id
    assert restored.name == corporate.name
    assert restored.representative_name == corporate.representative_name
    assert restored.status is corporate.status


async def test_処方箋が_入れ子の内容ごと復元できる(
    unit_of_work: PostgresUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Rp・用量・日付を含む集約がJSONBを往復しても壊れない。"""
    # Arrange
    prescription = create_prescription()

    # Act
    async with unit_of_work:
        await PostgresPrescriptionRepository(unit_of_work).save(prescription)
        await unit_of_work.commit()

    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        restored = await PostgresPrescriptionRepository(reader).get(
            corporate_id=prescription.corporate_id,
            prescription_id=prescription.id,
        )

    # Assert
    assert restored is not None
    assert restored.rps == prescription.rps
    assert restored.period == prescription.period
    assert restored.prescriber == prescription.prescriber
    assert restored.medical_institution == prescription.medical_institution


async def test_commitしないと_保存が残らない(
    unit_of_work: PostgresUnitOfWork,
    engine: AsyncEngine,
) -> None:
    """__aexit__ の巻き戻しが実サーバでも効いている。"""
    # Arrange
    corporate = create_corporate()

    # Act
    async with unit_of_work:
        await PostgresCorporateRepository(unit_of_work).save(corporate)

    # Assert
    assert await _count(engine, "corporates") == 0


# --------------------------------------------------------------------------
# 原子的なupsertと楽観ロック
# --------------------------------------------------------------------------


async def test_同一IDの2回目の保存が_行を増やさず世代を進める(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """ON CONFLICT DO UPDATE が実際に更新へ落ちる。"""
    # Arrange
    corporate = create_corporate()
    first = PostgresUnitOfWork(session_factory)
    async with first:
        await PostgresCorporateRepository(first).save(corporate)
        await first.commit()

    # Act
    second = PostgresUnitOfWork(session_factory)
    async with second:
        repository = PostgresCorporateRepository(second)
        loaded = await repository.get(corporate.id)
        assert loaded is not None
        await repository.save(loaded.change_name(loaded.name))
        await second.commit()

    # Assert
    assert await _count(engine, "corporates") == 1
    assert await _stored_version(engine, corporate) == 2


async def test_先に別トランザクションが更新すると_同時更新エラーになる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """読み込み後に割り込まれた更新を、後勝ちで踏み潰さない。"""
    # Arrange
    corporate = create_corporate()
    setup = PostgresUnitOfWork(session_factory)
    async with setup:
        await PostgresCorporateRepository(setup).save(corporate)
        await setup.commit()

    slow = PostgresUnitOfWork(session_factory)
    async with slow:
        slow_repository = PostgresCorporateRepository(slow)
        stale = await slow_repository.get(corporate.id)
        assert stale is not None

        # Act: 割り込んだ側が先に確定する
        fast = PostgresUnitOfWork(session_factory)
        async with fast:
            fast_repository = PostgresCorporateRepository(fast)
            fresh = await fast_repository.get(corporate.id)
            assert fresh is not None
            await fast_repository.save(fresh.deactivate())
            await fast.commit()

        # Assert: 古い世代を前提にした保存は拒否される
        with pytest.raises(ConcurrentModificationError):
            await slow_repository.save(stale.change_name(stale.name))

    # 割り込んだ側の更新は残っている
    assert await _stored_version(engine, corporate) == 2


async def test_未読の集約が既に存在すると_同時更新エラーになる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """新規のつもりの保存が既存行に当たったら、黙って捨てない。"""
    # Arrange
    corporate = create_corporate()
    first = PostgresUnitOfWork(session_factory)
    async with first:
        await PostgresCorporateRepository(first).save(corporate)
        await first.commit()

    # Act & Assert
    second = PostgresUnitOfWork(session_factory)
    async with second:
        with pytest.raises(ConcurrentModificationError):
            await PostgresCorporateRepository(second).save(corporate)


# --------------------------------------------------------------------------
# 一意制約の最終防衛
# --------------------------------------------------------------------------


async def test_法人名の重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """asyncpg が返す制約名を業務例外へ写像できている。"""
    # Arrange
    first = PostgresUnitOfWork(session_factory)
    async with first:
        await PostgresCorporateRepository(first).save(create_corporate("同じ名前薬局"))
        await first.commit()

    # Act & Assert
    second = PostgresUnitOfWork(session_factory)
    async with second:
        with pytest.raises(CorporateNameAlreadyExistsError):
            await PostgresCorporateRepository(second).save(
                create_corporate("同じ名前薬局")
            )


async def test_電子処方箋の引換番号の重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """引換番号の重複は二重取り込みを意味するので、DBが原子的に弾く。"""
    # Arrange
    corporate_id = CorporateId.generate()
    document_number = "1234567890123456"
    existing = create_prescription(
        corporate_id=corporate_id,
        source_type=PrescriptionSourceType.ELECTRONIC,
        document_number=document_number,
    )
    duplicate = create_prescription(
        corporate_id=corporate_id,
        source_type=PrescriptionSourceType.ELECTRONIC,
        document_number=document_number,
    )
    first = PostgresUnitOfWork(session_factory)
    async with first:
        await PostgresPrescriptionRepository(first).save(existing)
        await first.commit()

    # Act & Assert
    second = PostgresUnitOfWork(session_factory)
    async with second:
        with pytest.raises(PrescriptionDocumentNumberAlreadyExistsError):
            await PostgresPrescriptionRepository(second).save(duplicate)


async def test_紙処方箋は_同じ番号でも保存できる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """紙の番号は医療機関ごとの採番なので、一意性を課すと正当な処方箋を弾く。

    部分一意インデックスが電子処方箋だけを対象にしていることの確認。
    """
    # Arrange
    corporate_id = CorporateId.generate()
    document_number = "0000000000000001"
    first_paper = create_prescription(
        corporate_id=corporate_id,
        source_type=PrescriptionSourceType.PAPER_QR,
        document_number=document_number,
    )
    second_paper = create_prescription(
        corporate_id=corporate_id,
        source_type=PrescriptionSourceType.PAPER_QR,
        document_number=document_number,
    )

    # Act
    for prescription in (first_paper, second_paper):
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresPrescriptionRepository(unit_of_work).save(prescription)
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "prescriptions") == 2


async def test_別法人なら_同じ引換番号を保存できる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """一意性はテナント内で閉じる。"""
    # Arrange
    document_number = "9999999999999999"
    prescriptions = [
        create_prescription(
            corporate_id=CorporateId.generate(),
            source_type=PrescriptionSourceType.ELECTRONIC,
            document_number=document_number,
        )
        for _ in range(2)
    ]

    # Act
    for prescription in prescriptions:
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresPrescriptionRepository(unit_of_work).save(prescription)
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "prescriptions") == 2


async def test_調剤回数の重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同じ回の二重登録は、算定回数と薬歴の両方を二重にする。"""
    # Arrange
    corporate_id = CorporateId.generate()
    prescription = create_prescription(corporate_id=corporate_id)
    existing = create_dispensing(
        corporate_id=corporate_id, prescription_id=prescription.id, iteration=1
    )
    duplicate = create_dispensing(
        corporate_id=corporate_id, prescription_id=prescription.id, iteration=1
    )
    first = PostgresUnitOfWork(session_factory)
    async with first:
        await PostgresDispensingProcessRepository(first).save(existing)
        await first.commit()

    # Act & Assert
    second = PostgresUnitOfWork(session_factory)
    async with second:
        with pytest.raises(DispensingAlreadyExistsError):
            await PostgresDispensingProcessRepository(second).save(duplicate)


async def test_同じ処方箋の別の回は_保存できる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """リフィル・分割調剤の2回目以降を弾いてはいけない。"""
    # Arrange
    corporate_id = CorporateId.generate()
    prescription = create_prescription(corporate_id=corporate_id)

    # Act
    for iteration in (1, 2, 3):
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresDispensingProcessRepository(unit_of_work).save(
                create_dispensing(
                    corporate_id=corporate_id,
                    prescription_id=prescription.id,
                    iteration=iteration,
                )
            )
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "dispensing_processes") == 3


# --------------------------------------------------------------------------
# テナント境界と検索
# --------------------------------------------------------------------------


async def test_別法人の処方箋は_取得できない(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """他テナントのデータは存在を隠すため404相当のNoneに畳み込む。"""
    # Arrange
    prescription = create_prescription()
    setup = PostgresUnitOfWork(session_factory)
    async with setup:
        await PostgresPrescriptionRepository(setup).save(prescription)
        await setup.commit()

    # Act
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        found = await PostgresPrescriptionRepository(reader).get(
            corporate_id=CorporateId.generate(),
            prescription_id=prescription.id,
        )

    # Assert
    assert found is None


async def test_患者で絞った一覧が_他患者を含まない(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """一覧のWHERE句がテナントと患者の両方で効いている。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    target = create_prescription(corporate_id=corporate_id, patient_id=patient_id)
    other = create_prescription(
        corporate_id=corporate_id, patient_id=PatientId.generate()
    )
    setup = PostgresUnitOfWork(session_factory)
    async with setup:
        repository = PostgresPrescriptionRepository(setup)
        await repository.save(target)
        await repository.save(other)
        await setup.commit()

    # Act
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        found = await PostgresPrescriptionRepository(reader).list_by_patient(
            corporate_id=corporate_id, patient_id=patient_id
        )

    # Assert
    assert [prescription.id for prescription in found] == [target.id]


async def test_引換番号での検索が_法人内に閉じる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """他法人の同じ番号を引いてしまうとテナント境界が壊れる。"""
    # Arrange
    prescription = create_prescription(
        source_type=PrescriptionSourceType.ELECTRONIC,
        document_number="1111222233334444",
    )
    setup = PostgresUnitOfWork(session_factory)
    async with setup:
        await PostgresPrescriptionRepository(setup).save(prescription)
        await setup.commit()

    # Act
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        repository = PostgresPrescriptionRepository(reader)
        same_tenant = await repository.get_by_document_number(
            corporate_id=prescription.corporate_id,
            document_number=PrescriptionDocumentNumber("1111222233334444"),
        )
        other_tenant = await repository.get_by_document_number(
            corporate_id=CorporateId.generate(),
            document_number=PrescriptionDocumentNumber("1111222233334444"),
        )

    # Assert
    assert same_tenant is not None
    assert other_tenant is None


# --------------------------------------------------------------------------
# マイグレーションが作った実物
# --------------------------------------------------------------------------


async def test_マイグレーションが_電子処方箋だけの部分一意インデックスを作る(
    engine: AsyncEngine,
) -> None:
    """条件付きインデックスは、定義を読むだけでは効いているか分からない。"""
    # Arrange & Act
    async with engine.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE indexname = 'uq_prescriptions_electronic_document_number'"
            )
        )
        definition = result.scalar_one()

    # Assert
    assert "UNIQUE INDEX" in definition
    assert "WHERE" in definition
    assert "electronic" in definition


async def test_payloadが_JSONBとして問い合わせできる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """文字列として保存されていると、後からの検索も部分更新もできなくなる。"""
    # Arrange
    corporate = create_corporate("JSONB確認薬局")
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresCorporateRepository(unit_of_work).save(corporate)
        await unit_of_work.commit()

    # Act
    async with engine.connect() as connection:
        result = await connection.execute(
            text("SELECT payload ->> 'name' FROM corporates WHERE id = :id"),
            {"id": corporate.id.value},
        )
        name_in_payload = result.scalar_one()

    # Assert
    assert name_in_payload == "JSONB確認薬局"
