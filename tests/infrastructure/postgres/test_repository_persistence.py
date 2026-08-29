"""PostgreSQL Repository の保存経路（原子的なupsertと楽観ロック）を検査する。"""

from __future__ import annotations

import pytest

from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.foundation.exceptions import ConcurrentModificationError
from app.domain.prescription.exceptions import (
    PrescriptionDocumentNumberAlreadyExistsError,
)
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    encode_aggregate,
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
from tests.factories.dispensing_factory import create_dispensing
from tests.factories.prescription_factory import create_prescription
from tests.fakes.recording_async_session import FakeResult, RecordingAsyncSession
from tests.infrastructure.postgres.helpers import (
    compiled_params,
    compiled_sql,
    create_corporate,
    create_unit_of_work,
    integrity_error,
)


async def test_未読の集約の保存が_衝突時に何もしないINSERTになる() -> None:
    """事前SELECTで存在確認をすると、同時INSERTが主キー違反として漏れる。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)
    corporate = create_corporate()

    # Act
    async with unit_of_work:
        await PostgresCorporateRepository(unit_of_work).save(corporate)

    # Assert
    assert len(session.executed) == 1, "保存前のSELECTは原子性の代替にならない。"
    sql = compiled_sql(session.executed[0])
    assert "INSERT INTO corporates" in sql
    assert "ON CONFLICT (id) DO NOTHING" in sql
    assert compiled_params(session.executed[0])["version"] == 1


async def test_読み込んだ集約の保存が_同じ世代の行だけを更新する() -> None:
    """読み込み後に他トランザクションが更新していたら上書きしない。"""
    # Arrange
    corporate = create_corporate()
    row = {
        "id": corporate.id.value,
        "name": corporate.name.value,
        "representative_name": corporate.representative_name.full_name,
        "status": corporate.status.value,
        "payload": encode_aggregate(corporate),
        "version": 7,
    }
    session = RecordingAsyncSession(results=[FakeResult(rows=[row])])
    unit_of_work = create_unit_of_work(session)

    # Act
    async with unit_of_work:
        repository = PostgresCorporateRepository(unit_of_work)
        loaded = await repository.get(corporate.id)
        assert loaded is not None
        await repository.save(loaded)

    # Assert
    sql = compiled_sql(session.executed[-1])
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert "WHERE corporates.version = " in sql
    assert compiled_params(session.executed[-1])["version"] == 8


async def test_更新が0行なら_同時更新エラーになる() -> None:
    """世代が合わない＝読み込み後に別の誰かが書いた、ということ。"""
    # Arrange
    corporate = create_corporate()
    row = {
        "id": corporate.id.value,
        "name": corporate.name.value,
        "representative_name": corporate.representative_name.full_name,
        "status": corporate.status.value,
        "payload": encode_aggregate(corporate),
        "version": 2,
    }
    session = RecordingAsyncSession(
        results=[FakeResult(rows=[row]), FakeResult(rowcount=0)]
    )
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        repository = PostgresCorporateRepository(unit_of_work)
        loaded = await repository.get(corporate.id)
        assert loaded is not None
        with pytest.raises(ConcurrentModificationError):
            await repository.save(loaded)


async def test_未読の集約が既に存在すると_同時更新エラーになる() -> None:
    """新規のつもりの保存が既存行に当たったら、黙って捨てずに知らせる。"""
    # Arrange
    session = RecordingAsyncSession(results=[FakeResult(rowcount=0)])
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(ConcurrentModificationError):
            await PostgresCorporateRepository(unit_of_work).save(create_corporate())


async def test_保存を繰り返すと_世代が積み上がる() -> None:
    """同一トランザクション内の2回目の保存は、1回目が書いた世代を前提にする。"""
    # Arrange
    session = RecordingAsyncSession()
    unit_of_work = create_unit_of_work(session)
    corporate = create_corporate()

    # Act
    async with unit_of_work:
        repository = PostgresCorporateRepository(unit_of_work)
        await repository.save(corporate)
        await repository.save(corporate)

    # Assert
    assert compiled_params(session.executed[0])["version"] == 1
    assert compiled_params(session.executed[1])["version"] == 2
    assert "ON CONFLICT (id) DO UPDATE" in compiled_sql(session.executed[1])


async def test_法人名の一意制約違反が_業務例外へ写像される() -> None:
    """DBの制約名を業務例外へ翻訳しないと、呼び出し側が扱えない。"""
    # Arrange
    session = RecordingAsyncSession()
    session.error = integrity_error("uq_corporates_name")
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(CorporateNameAlreadyExistsError):
            await PostgresCorporateRepository(unit_of_work).save(create_corporate())


async def test_想定外の制約違反は_そのまま送出される() -> None:
    """知らない制約を業務例外へ丸めると、原因が消える。"""
    # Arrange
    session = RecordingAsyncSession()
    session.error = integrity_error("ck_corporates_unknown")
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(Exception) as error:
            await PostgresCorporateRepository(unit_of_work).save(create_corporate())
    assert not isinstance(error.value, CorporateNameAlreadyExistsError)


async def test_電子処方箋番号の重複が_業務例外へ写像される() -> None:
    """部分一意インデックス違反は二重取り込みを意味する。"""
    # Arrange
    session = RecordingAsyncSession()
    session.error = integrity_error("uq_prescriptions_electronic_document_number")
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(PrescriptionDocumentNumberAlreadyExistsError):
            await PostgresPrescriptionRepository(unit_of_work).save(
                create_prescription()
            )


async def test_調剤回数の重複が_業務例外へ写像される() -> None:
    """同じ回の調剤が二重に登録されると、算定回数と薬歴が二重になる。"""
    # Arrange
    session = RecordingAsyncSession()
    session.error = integrity_error("uq_dispensing_processes_prescription_iteration")
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(DispensingAlreadyExistsError):
            await PostgresDispensingProcessRepository(unit_of_work).save(
                create_dispensing()
            )


async def test_検索列とpayloadが食い違う行は_復元を拒否する() -> None:
    """列だけ書き換えられた行を読み込むと、集約と行の意味がずれる。"""
    # Arrange
    corporate = create_corporate()
    row = {
        "id": corporate.id.value,
        "name": "別の名前",
        "representative_name": corporate.representative_name.full_name,
        "status": corporate.status.value,
        "payload": encode_aggregate(corporate),
        "version": 1,
    }
    session = RecordingAsyncSession(results=[FakeResult(rows=[row])])
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(PersistenceMappingError):
            await PostgresCorporateRepository(unit_of_work).get(corporate.id)


async def test_version列の無い行は_復元を拒否する() -> None:
    """世代が分からない行を読むと、保存時に黙って上書きしてしまう。"""
    # Arrange
    corporate = create_corporate()
    row = {
        "id": corporate.id.value,
        "name": corporate.name.value,
        "representative_name": corporate.representative_name.full_name,
        "status": corporate.status.value,
        "payload": encode_aggregate(corporate),
    }
    session = RecordingAsyncSession(results=[FakeResult(rows=[row])])
    unit_of_work = create_unit_of_work(session)

    # Act & Assert
    async with unit_of_work:
        with pytest.raises(PersistenceMappingError):
            await PostgresCorporateRepository(unit_of_work).get(corporate.id)


async def test_存在しない集約の検索は_Noneを返す() -> None:
    """他法人のデータは存在を隠すため、404相当のNoneに畳み込む。"""
    # Arrange
    session = RecordingAsyncSession(results=[FakeResult(rows=[])])
    unit_of_work = create_unit_of_work(session)
    prescription = create_prescription()

    # Act
    async with unit_of_work:
        found = await PostgresPrescriptionRepository(unit_of_work).get(
            corporate_id=prescription.corporate_id,
            prescription_id=prescription.id,
        )

    # Assert
    assert found is None
