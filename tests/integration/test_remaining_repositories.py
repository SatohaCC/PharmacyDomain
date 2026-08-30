"""残る集約の PostgreSQL Repository を実DBで検証する。

一意制約・部分一意インデックス・排他制約は、定義を読むだけでは「どの行を弾くか」が
分からない。特に期間の重なりを拒否する排他制約は、境界の日を1日ずらすだけで挙動が
変わるため、実サーバで確かめる。
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domain.corporate.primitives import CorporateId
from app.domain.coverage.exceptions import CoveragePeriodConflictError
from app.domain.coverage.primitives import CoverageDeactivatedOn
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyExistsError,
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medicine_catalog.exceptions import (
    MedicineEffectivePeriodConflictError,
)
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientId,
)
from app.domain.staff.exceptions import StaffCodeAlreadyExistsError
from app.domain.staff.primitives import StaffCode
from app.domain.store.exceptions import (
    InsurancePharmacyNumberAlreadyExistsError,
    StoreCodeAlreadyExistsError,
    StoreNameAlreadyExistsError,
)
from app.domain.store.primitives import StoreName
from app.infrastructure.postgres.repositories.corporate import (
    PostgresCorporateRepository,
)
from app.infrastructure.postgres.repositories.coverage import (
    PostgresPatientCoverageRepository,
)
from app.infrastructure.postgres.repositories.medication_history import (
    PostgresMedicationHistoryRepository,
    PostgresPatientMedicalProfileRepository,
)
from app.infrastructure.postgres.repositories.medicine_catalog import (
    PostgresMedicineCatalogRepository,
)
from app.infrastructure.postgres.repositories.patient import (
    PostgresPatientExternalIdentifierRepository,
    PostgresPatientRepository,
)
from app.infrastructure.postgres.repositories.reception import (
    PostgresCoverageSelectionRecordRepository,
)
from app.infrastructure.postgres.repositories.staff import PostgresStaffRepository
from app.infrastructure.postgres.repositories.store import PostgresStoreRepository
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork
from tests.factories.medication_history_factory import create_record
from tests.factories.medicine_catalog_factory import create_identifier, create_medicine
from tests.factories.persistence_factory import (
    create_coverage,
    create_external_identifier,
    create_medical_profile,
    create_patient,
    create_selection_record,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
from tests.infrastructure.postgres.helpers import create_corporate


async def _committed_corporate(
    session_factory: async_sessionmaker[AsyncSession],
    name: str = "結合テスト法人",
) -> CorporateId:
    """外部キーの参照先になる法人を確定させる。"""
    corporate = create_corporate(name)
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresCorporateRepository(unit_of_work).save(corporate)
        await unit_of_work.commit()
    return corporate.id


async def _count(engine: AsyncEngine, table_name: str) -> int:
    """テーブルの行数を直接読む。"""
    async with engine.connect() as connection:
        result = await connection.execute(text(f"SELECT count(*) FROM {table_name}"))
        return int(result.scalar_one())


# --------------------------------------------------------------------------
# 店舗
# --------------------------------------------------------------------------


async def test_店舗が_復元できて店舗名の重複を拒否する(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同一法人内の店舗名は一意。"""
    # Arrange
    corporate_id = await _committed_corporate(session_factory)
    store = create_store(corporate_id=corporate_id, name="一号店")

    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresStoreRepository(unit_of_work).save(store)
        await unit_of_work.commit()

    # Act
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        repository = PostgresStoreRepository(reader)
        restored = await repository.get(store.id)
        used = await repository.exists_by_name(
            corporate_id=corporate_id, name=StoreName("一号店")
        )

    # Assert
    assert restored is not None
    assert restored.names.name == store.names.name
    assert used is True

    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(StoreNameAlreadyExistsError):
            await PostgresStoreRepository(conflict).save(
                create_store(corporate_id=corporate_id, name="一号店")
            )


async def test_店舗コードの重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """店舗コードは同一法人内で一意。"""
    # Arrange
    corporate_id = await _committed_corporate(session_factory)
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresStoreRepository(unit_of_work).save(
            create_store(corporate_id=corporate_id, name="一号店", code="S001")
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(StoreCodeAlreadyExistsError):
            await PostgresStoreRepository(conflict).save(
                create_store(corporate_id=corporate_id, name="二号店", code="S001")
            )


async def test_店舗コード未設定の店舗は_何件でも保存できる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """任意項目の未設定どうしを衝突させると、正当な登録を弾いてしまう。"""
    # Arrange
    corporate_id = await _committed_corporate(session_factory)

    # Act
    for name in ("一号店", "二号店", "三号店"):
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresStoreRepository(unit_of_work).save(
                create_store(corporate_id=corporate_id, name=name)
            )
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "stores") == 3


async def test_保険薬局指定番号の重複が_法人をまたいで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """指定番号は国が付番するので、法人が違っても重複しえない。"""
    # Arrange
    first_corporate = await _committed_corporate(session_factory, "法人A")
    second_corporate = await _committed_corporate(session_factory, "法人B")
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresStoreRepository(unit_of_work).save(
            create_store(
                corporate_id=first_corporate,
                name="一号店",
                insurance_pharmacy_number="1341234567",
            )
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(InsurancePharmacyNumberAlreadyExistsError):
            await PostgresStoreRepository(conflict).save(
                create_store(
                    corporate_id=second_corporate,
                    name="別法人の店",
                    insurance_pharmacy_number="1341234567",
                )
            )


async def test_存在しない法人の店舗は_外部キーで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """法人の実在確認はApplication層が行うが、最終防衛はDBが持つ。"""
    # Arrange
    store = create_store(corporate_id=CorporateId.generate(), name="宙に浮いた店")

    # Act & Assert
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        with pytest.raises(Exception) as error:
            await PostgresStoreRepository(unit_of_work).save(store)
    assert "fk_stores_corporate_id_corporates" in str(error.value)


# --------------------------------------------------------------------------
# スタッフ
# --------------------------------------------------------------------------


async def test_スタッフコードの重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同一法人内のスタッフコードは一意。"""
    # Arrange
    corporate_id = await _committed_corporate(session_factory)
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresStaffRepository(unit_of_work).save(
            create_staff(corporate_id=corporate_id, code="P001")
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(StaffCodeAlreadyExistsError):
            await PostgresStaffRepository(conflict).save(
                create_staff(corporate_id=corporate_id, code="P001")
            )


async def test_無効化したスタッフのコードは_再利用できない(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """過去の調剤録・監査の追跡を壊さないため、無効化しても解放しない。

    有効行だけを一意とする外部識別子とは逆の判断であり、ここが取り違えやすい。
    """
    # Arrange
    corporate_id = await _committed_corporate(session_factory)
    staff = create_staff(corporate_id=corporate_id, code="P001")
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        repository = PostgresStaffRepository(unit_of_work)
        await repository.save(staff)
        await unit_of_work.commit()

    deactivate = PostgresUnitOfWork(session_factory)
    async with deactivate:
        repository = PostgresStaffRepository(deactivate)
        loaded = await repository.get(corporate_id=corporate_id, staff_id=staff.id)
        assert loaded is not None
        await repository.save(loaded.deactivate(date(2026, 3, 31)))
        await deactivate.commit()

    # Act & Assert
    reuse = PostgresUnitOfWork(session_factory)
    async with reuse:
        repository = PostgresStaffRepository(reuse)
        assert await repository.exists_by_code(
            corporate_id=corporate_id, code=StaffCode("P001")
        )
        with pytest.raises(StaffCodeAlreadyExistsError):
            await repository.save(create_staff(corporate_id=corporate_id, code="P001"))


# --------------------------------------------------------------------------
# 患者と外部識別子
# --------------------------------------------------------------------------


async def test_患者番号の採番が_法人ごとに連番になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """採番と加算が1文で閉じるので、同時受付でも同じ番号は出ない。"""
    # Arrange
    first_corporate = CorporateId.generate()
    second_corporate = CorporateId.generate()

    # Act
    allocated: list[int] = []
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        repository = PostgresPatientRepository(unit_of_work)
        for _ in range(3):
            allocated.append(
                (await repository.allocate_patient_number(first_corporate)).value
            )
        other = await repository.allocate_patient_number(second_corporate)
        await unit_of_work.commit()

    # Assert
    assert allocated == [1, 2, 3]
    assert other.value == 1, "法人が違えば採番は独立している。"


async def test_患者番号の重複が_DBで拒否される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """採番を通さず同じ番号を作ると、一意制約が最終防衛になる。"""
    # Arrange
    corporate_id = CorporateId.generate()
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresPatientRepository(unit_of_work).save(
            create_patient(corporate_id=corporate_id, patient_number=1)
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(Exception) as error:
            await PostgresPatientRepository(conflict).save(
                create_patient(corporate_id=corporate_id, patient_number=1)
            )
    assert "uq_patients_corporate_number" in str(error.value)


async def test_有効な外部IDの重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """同一法人・連携先・外部患者IDの有効行は1件だけ。"""
    # Arrange
    corporate_id = CorporateId.generate()
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresPatientExternalIdentifierRepository(unit_of_work).save(
            create_external_identifier(corporate_id=corporate_id)
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(PatientExternalIdentifierAlreadyExistsError):
            await PostgresPatientExternalIdentifierRepository(conflict).save(
                create_external_identifier(corporate_id=corporate_id)
            )


async def test_無効化した外部IDは_別の患者へ付け替えられる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """誤った患者へ紐付けた外部IDを、無効化してから正しい患者へ移せる。

    スタッフコードとは逆に、一意とみなすのは有効な行だけ。
    """
    # Arrange
    corporate_id = CorporateId.generate()
    wrong = create_external_identifier(corporate_id=corporate_id)
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresPatientExternalIdentifierRepository(unit_of_work).save(wrong)
        await unit_of_work.commit()

    deactivate = PostgresUnitOfWork(session_factory)
    async with deactivate:
        repository = PostgresPatientExternalIdentifierRepository(deactivate)
        loaded = await repository.get(corporate_id=corporate_id, identifier_id=wrong.id)
        assert loaded is not None
        await repository.save(loaded.deactivate())
        await deactivate.commit()

    # Act
    correct_patient = PatientId.generate()
    reassign = PostgresUnitOfWork(session_factory)
    async with reassign:
        await PostgresPatientExternalIdentifierRepository(reassign).save(
            create_external_identifier(
                corporate_id=corporate_id, patient_id=correct_patient
            )
        )
        await reassign.commit()

    # Assert
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        active = await PostgresPatientExternalIdentifierRepository(
            reader
        ).get_active_by_source(
            corporate_id=corporate_id,
            system_name=ExternalSystemName("レセコンA"),
            external_patient_id=ExternalPatientId("EXT-001"),
        )
    assert active is not None
    assert active.patient_id == correct_patient


# --------------------------------------------------------------------------
# 患者資格（排他制約）
# --------------------------------------------------------------------------


async def test_同一順位で期間が重なる資格が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """期間の重なりは一意制約では表せないので排他制約が担う。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresPatientCoverageRepository(unit_of_work).save(
            create_coverage(
                corporate_id=corporate_id,
                patient_id=patient_id,
                valid_from=date(2026, 8, 1),
                valid_to=date(2026, 8, 31),
            )
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(CoveragePeriodConflictError):
            await PostgresPatientCoverageRepository(conflict).save(
                create_coverage(
                    corporate_id=corporate_id,
                    patient_id=patient_id,
                    valid_from=date(2026, 8, 31),
                    valid_to=date(2026, 9, 30),
                )
            )


async def test_期間が1日ずれた資格は_保存できる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """終了日は期間に**含む**。翌日から始まる資格は重ならない。

    半開区間として範囲を作ると、この組み合わせを誤って弾く。
    """
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    periods = [
        (date(2026, 8, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 30)),
    ]

    # Act
    for valid_from, valid_to in periods:
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresPatientCoverageRepository(unit_of_work).save(
                create_coverage(
                    corporate_id=corporate_id,
                    patient_id=patient_id,
                    valid_from=valid_from,
                    valid_to=valid_to,
                )
            )
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "patient_coverages") == 2


async def test_順位が違えば_同じ期間でも併用できる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """第一公費と第二公費は同時に有効になりうる。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()

    # Act
    for priority in (1, 2):
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresPatientCoverageRepository(unit_of_work).save(
                create_coverage(
                    corporate_id=corporate_id,
                    patient_id=patient_id,
                    priority=priority,
                )
            )
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "patient_coverages") == 2


async def test_無効化した資格は_同じ期間の新しい資格を妨げない(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """実効期間が空になった行は競合判定の対象から外れる。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    coverage = create_coverage(
        corporate_id=corporate_id,
        patient_id=patient_id,
        valid_from=date(2026, 8, 1),
        valid_to=date(2026, 8, 31),
    )
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresPatientCoverageRepository(unit_of_work).save(coverage)
        await unit_of_work.commit()

    deactivate = PostgresUnitOfWork(session_factory)
    async with deactivate:
        repository = PostgresPatientCoverageRepository(deactivate)
        loaded = await repository.get(
            corporate_id=corporate_id, coverage_id=coverage.id
        )
        assert loaded is not None
        # 開始日当日に無効化すると、実効期間は空になる。
        await repository.save(
            loaded.deactivate(CoverageDeactivatedOn(date(2026, 8, 1)))
        )
        await deactivate.commit()

    # Act
    replacement = PostgresUnitOfWork(session_factory)
    async with replacement:
        await PostgresPatientCoverageRepository(replacement).save(
            create_coverage(
                corporate_id=corporate_id,
                patient_id=patient_id,
                valid_from=date(2026, 8, 1),
                valid_to=date(2026, 8, 31),
            )
        )
        await replacement.commit()

    # Assert
    assert await _count(engine, "patient_coverages") == 2


# --------------------------------------------------------------------------
# 資格選択履歴
# --------------------------------------------------------------------------


async def test_資格選択履歴が_最新1件を返す(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """履歴は積み上げ、初期候補には最新だけを使う。"""
    # Arrange
    from datetime import UTC, datetime

    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    first = create_selection_record(
        corporate_id=corporate_id,
        patient_id=patient_id,
        recorded_at=datetime(2026, 8, 20, 1, 0, tzinfo=UTC),
    )
    latest = create_selection_record(
        corporate_id=corporate_id,
        store_id=first.store_id,
        patient_id=patient_id,
        recorded_at=datetime(2026, 8, 23, 1, 0, tzinfo=UTC),
    )

    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        repository = PostgresCoverageSelectionRecordRepository(unit_of_work)
        await repository.save(first)
        await repository.save(latest)
        await unit_of_work.commit()

    # Act
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        found = await PostgresCoverageSelectionRecordRepository(reader).get_latest(
            corporate_id=corporate_id,
            store_id=first.store_id,
            patient_id=patient_id,
        )

    # Assert
    assert found is not None
    assert found.id == latest.id
    assert found.selection == latest.selection, "枠構造がそのまま復元される。"


# --------------------------------------------------------------------------
# 薬歴と頭書き
# --------------------------------------------------------------------------


async def test_同一調剤の確定済薬歴の重複が_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """1回の調剤に対する指導記録が二重になると、算定も投影も二重になる。"""
    # Arrange
    corporate_id = CorporateId.generate()
    first = create_record(corporate_id=corporate_id).finalize()
    duplicate = create_record(
        corporate_id=corporate_id, dispensing_id=first.dispensing_id
    ).finalize()

    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresMedicationHistoryRepository(unit_of_work).save(first)
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(MedicationHistoryAlreadyExistsError):
            await PostgresMedicationHistoryRepository(conflict).save(duplicate)


async def test_下書きの薬歴は_同じ調剤に何件でも作れる(
    session_factory: async_sessionmaker[AsyncSession],
    engine: AsyncEngine,
) -> None:
    """書きかけを複数持つのは正当なので、下書きは制限しない。"""
    # Arrange
    corporate_id = CorporateId.generate()
    first = create_record(corporate_id=corporate_id)

    # Act
    for _ in range(3):
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresMedicationHistoryRepository(unit_of_work).save(
                create_record(
                    corporate_id=corporate_id, dispensing_id=first.dispensing_id
                )
            )
            await unit_of_work.commit()

    # Assert
    assert await _count(engine, "medication_history_records") == 3


async def test_頭書きが_患者ごとに1件へ制限される(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """頭書きが2件あると、どちらが投影結果かが決まらない。"""
    # Arrange
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresPatientMedicalProfileRepository(unit_of_work).save(
            create_medical_profile(corporate_id=corporate_id, patient_id=patient_id)
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(PatientMedicalProfileAlreadyExistsError):
            await PostgresPatientMedicalProfileRepository(conflict).save(
                create_medical_profile(corporate_id=corporate_id, patient_id=patient_id)
            )


# --------------------------------------------------------------------------
# 医薬品マスタ（排他制約・時点検索）
# --------------------------------------------------------------------------


async def test_同一薬品コードで期間が重なると_業務例外になる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """期間が重なると、ある日付で引いたときに2行返ってしまう。"""
    # Arrange
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        await PostgresMedicineCatalogRepository(unit_of_work).save(
            create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=date(2024, 3, 31))
        )
        await unit_of_work.commit()

    # Act & Assert
    conflict = PostgresUnitOfWork(session_factory)
    async with conflict:
        with pytest.raises(MedicineEffectivePeriodConflictError):
            await PostgresMedicineCatalogRepository(conflict).save(
                create_medicine(
                    listed_on=date(2024, 3, 31), withdrawn_on=date(2026, 3, 31)
                )
            )


async def test_経過措置期限の翌日から始まる版は_保存できる(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """経過措置期限は「その日まで使える」。閉区間で扱わないと改定が入らない。"""
    # Arrange
    versions = [
        (date(2020, 4, 1), date(2024, 3, 31)),
        (date(2024, 4, 1), None),
    ]

    # Act
    for listed_on, withdrawn_on in versions:
        unit_of_work = PostgresUnitOfWork(session_factory)
        async with unit_of_work:
            await PostgresMedicineCatalogRepository(unit_of_work).save(
                create_medicine(listed_on=listed_on, withdrawn_on=withdrawn_on)
            )
            await unit_of_work.commit()

    # Assert
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        found = await PostgresMedicineCatalogRepository(reader).list_versions(
            create_identifier()
        )
    assert [medicine.effective_period.listed_on.value for medicine in found] == [
        date(2020, 4, 1),
        date(2024, 4, 1),
    ]


async def test_適用日で引くと_その時点の版が返る(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """「今」で引くと過去の調剤を新しいマスタで判定してしまう。"""
    # Arrange
    unit_of_work = PostgresUnitOfWork(session_factory)
    async with unit_of_work:
        repository = PostgresMedicineCatalogRepository(unit_of_work)
        await repository.save(
            create_medicine(
                name="旧版", listed_on=date(2020, 4, 1), withdrawn_on=date(2024, 3, 31)
            )
        )
        await repository.save(create_medicine(name="新版", listed_on=date(2024, 4, 1)))
        await unit_of_work.commit()

    # Act
    reader = PostgresUnitOfWork(session_factory)
    async with reader:
        repository = PostgresMedicineCatalogRepository(reader)
        old_version = await repository.find_effective(
            identifier=create_identifier(), as_of=date(2022, 6, 1)
        )
        boundary = await repository.find_effective(
            identifier=create_identifier(), as_of=date(2024, 3, 31)
        )
        new_version = await repository.find_effective(
            identifier=create_identifier(), as_of=date(2025, 1, 1)
        )
        missing = await repository.find_effective(
            identifier=create_identifier(), as_of=date(2019, 1, 1)
        )

    # Assert
    assert old_version is not None
    assert old_version.name.value == "旧版"
    assert boundary is not None
    assert boundary.name.value == "旧版", "経過措置期限の当日はまだ有効。"
    assert new_version is not None
    assert new_version.name.value == "新版"
    assert missing is None
