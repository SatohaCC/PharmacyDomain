"""薬歴の頭書き再投影・患者ロック・待機後再読込のApplication層検証。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.common.exceptions import ApplicationError
from app.application.common.organization_lock import OrganizationLock
from app.application.medication_history.correct_medication_history_fact import (
    CorrectMedicationHistoryFactCommand,
    CorrectMedicationHistoryFactUseCase,
)
from app.application.medication_history.finalize_medication_history import (
    FinalizeMedicationHistoryCommand,
    FinalizeMedicationHistoryUseCase,
)
from app.application.medication_history.get_patient_medical_profile import (
    RebuildPatientMedicalProfileCommand,
    RebuildPatientMedicalProfileUseCase,
)
from app.application.medication_history.profile_projection_service import (
    PatientMedicalProfileProjectionService,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.medication_history.value_objects import (
    ProfileUpdateIntents,
)
from app.domain.patient.primitives import PatientId
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    create_fixture,
)
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_record,
    finalize_record_with_review,
)
from tests.fakes.fake_organization_management import FakeOrganizationLock
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryRepository,
)
from tests.fakes.in_memory_patient_medical_profile_repository import (
    InMemoryPatientMedicalProfileRepository,
)
from tests.fakes.null_unit_of_work import NullUnitOfWork


class _TrackingLock(OrganizationLock):
    """ロック取得順序とキーを記録する。"""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.keys: list[str] = []

    async def acquire(self, key: str) -> None:
        self.events.append(f"lock:{key}")
        self.keys.append(key)


class _TrackingMedicationHistoryRepository(InMemoryMedicationHistoryRepository):
    """リポジトリ呼出順序を記録する。"""

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    async def get(
        self, *, corporate_id: CorporateId, record_id: MedicationHistoryRecordId
    ) -> MedicationHistoryRecord | None:
        self.events.append("repo:get")
        return await super().get(corporate_id=corporate_id, record_id=record_id)

    async def save(self, record: MedicationHistoryRecord) -> None:
        self.events.append("repo:save")
        await super().save(record)

    async def list_for_profile_projection(
        self, *, corporate_id: CorporateId, patient_id: PatientId
    ) -> list[MedicationHistoryRecord]:
        self.events.append("repo:list_for_profile_projection")
        return await super().list_for_profile_projection(
            corporate_id=corporate_id, patient_id=patient_id
        )


class _TrackingProfileProjectionService(PatientMedicalProfileProjectionService):
    """投影サービスの呼出を追跡する。"""

    def __init__(
        self,
        record_repository: InMemoryMedicationHistoryRepository,
        profile_repository: InMemoryPatientMedicalProfileRepository,
        events: list[str],
    ) -> None:
        super().__init__(record_repository, profile_repository)
        self.events = events
        self.calls: list[tuple[CorporateId, PatientId]] = []

    async def project(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> PatientMedicalProfile:
        self.events.append("service:project")
        self.calls.append((corporate_id, patient_id))
        return await super().project(corporate_id=corporate_id, patient_id=patient_id)


class _InactiveUnitOfWork(NullUnitOfWork):
    """開始されていないUnit of Work。"""

    def ensure_active(self) -> None:
        raise ApplicationError("トランザクションが開始されていません。")


@pytest.mark.asyncio
async def test_3経路とも同一の患者キーでロックを先行取得する() -> None:
    """確定・訂正・手動再構築の全経路が、業務処理より前に同一形式の患者ロックを取る。"""
    fixture = create_fixture()
    expected_key = f"medication-history-retention:{fixture.corporate_id.value}:{fixture.patient_id.value}"

    # 1. 確定
    events_finalize: list[str] = []
    lock_finalize = _TrackingLock(events_finalize)
    repo_finalize = _TrackingMedicationHistoryRepository(events_finalize)
    draft_record = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
    )
    await repo_finalize.save(draft_record)
    events_finalize.clear()

    use_case_finalize = FinalizeMedicationHistoryUseCase(
        record_repository=repo_finalize,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=lock_finalize,
        category_catalog_repository=fixture.category_catalog_repository,
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        clock=fixture.clock,
    )
    await use_case_finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(draft_record.id.value),
            review_result="assessment_and_instruction_recorded",
        )
    )

    assert lock_finalize.keys == [expected_key]
    first_lock_idx = events_finalize.index(f"lock:{expected_key}")
    first_save_idx = events_finalize.index("repo:save")
    assert first_lock_idx < first_save_idx

    # 2. 訂正
    events_correct: list[str] = []
    lock_correct = _TrackingLock(events_correct)
    repo_correct = _TrackingMedicationHistoryRepository(events_correct)
    finalized_record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.counselor_id,
            counseled_at=datetime(2026, 9, 20, 4, tzinfo=UTC),
        )
    )
    await repo_correct.save(finalized_record)
    events_correct.clear()

    use_case_correct = CorrectMedicationHistoryFactUseCase(
        record_repository=repo_correct,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=lock_correct,
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        category_catalog_repository=fixture.category_catalog_repository,
        store_operations=fixture.store_operations,
        clock=fixture.clock,
    )
    await use_case_correct.execute(
        CorrectMedicationHistoryFactCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(finalized_record.id.value),
            target="method",
            operation="replace",
            reason="事実訂正",
            value="face_to_face",
        )
    )

    assert lock_correct.keys == [expected_key]
    correct_lock_idx = events_correct.index(f"lock:{expected_key}")
    correct_save_idx = events_correct.index("repo:save")
    assert correct_lock_idx < correct_save_idx

    # 3. 手動再構築
    events_rebuild: list[str] = []
    lock_rebuild = _TrackingLock(events_rebuild)
    repo_rebuild = _TrackingMedicationHistoryRepository(events_rebuild)
    await repo_rebuild.save(finalized_record)
    events_rebuild.clear()

    use_case_rebuild = RebuildPatientMedicalProfileUseCase(
        record_repository=repo_rebuild,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=lock_rebuild,
    )
    await use_case_rebuild.execute(
        RebuildPatientMedicalProfileCommand(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            as_of=datetime(2026, 9, 20, tzinfo=UTC).date(),
        )
    )

    assert lock_rebuild.keys == [expected_key]
    rebuild_lock_idx = events_rebuild.index(f"lock:{expected_key}")
    rebuild_proj_idx = events_rebuild.index("repo:list_for_profile_projection")
    assert rebuild_lock_idx < rebuild_proj_idx


@pytest.mark.asyncio
async def test_確定と訂正はロック待機後に対象薬歴を再読込する() -> None:
    """ロック待ちの間に別プロセスが薬歴を確定・更新した場合、待機後の最新状態に基づいて判定する。"""
    fixture = create_fixture()
    draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        counseled_at=fixture.clock.now() - timedelta(minutes=10),
    )
    await fixture.record_repository.save(draft)

    class _InterleavingFinalizeLock(OrganizationLock):
        """ロック取得の瞬間に、別トランザクションがすでに確定を完了した状態を再現する。"""

        def __init__(
            self,
            repo: InMemoryMedicationHistoryRepository,
            record_to_finalize: MedicationHistoryRecord,
        ) -> None:
            self._repo = repo
            self._record = record_to_finalize

        async def acquire(self, key: str) -> None:
            # 待機中に先行トランザクションが確定保存を完了
            already_finalized = finalize_record_with_review(self._record)
            await self._repo.save(already_finalized)

    interleaving_lock = _InterleavingFinalizeLock(fixture.record_repository, draft)
    use_case = FinalizeMedicationHistoryUseCase(
        record_repository=fixture.record_repository,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=interleaving_lock,
        category_catalog_repository=fixture.category_catalog_repository,
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        clock=fixture.clock,
    )

    # ロック待機後に再読込され、確定済みであるため二重確定エラーになる
    with pytest.raises(
        MedicationHistoryDomainError, match="確定済の薬歴は上書きできません"
    ):
        await use_case.execute(
            FinalizeMedicationHistoryCommand(
                corporate_id=str(fixture.corporate_id.value),
                record_id=str(draft.id.value),
                review_result="assessment_and_instruction_recorded",
            )
        )


@pytest.mark.asyncio
async def test_3経路すべてが共通のPatientMedicalProfileProjectionServiceを利用する() -> (
    None
):
    """確定・訂正・手動再構築のすべてが共通Projectionサービスへ委譲する。"""
    fixture = create_fixture()
    now = fixture.clock.now()
    record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            counselor_id=fixture.counselor_id,
            counseled_at=now - timedelta(minutes=30),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="アスピリン"),)
            ),
        )
    )
    draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        counselor_id=fixture.counselor_id,
        counseled_at=now - timedelta(minutes=10),
    )
    await fixture.record_repository.save(record)
    await fixture.record_repository.save(draft)

    events: list[str] = []
    projection_service = _TrackingProfileProjectionService(
        fixture.record_repository, fixture.profile_repository, events
    )
    lock = FakeOrganizationLock()

    # 1. 確定
    use_case_finalize = FinalizeMedicationHistoryUseCase(
        record_repository=fixture.record_repository,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=lock,
        category_catalog_repository=fixture.category_catalog_repository,
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        clock=fixture.clock,
        projection_service=projection_service,
    )
    await use_case_finalize.execute(
        FinalizeMedicationHistoryCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(draft.id.value),
            review_result="assessment_and_instruction_recorded",
        )
    )
    assert (fixture.corporate_id, fixture.patient_id) in projection_service.calls

    # 2. 訂正
    projection_service.calls.clear()
    use_case_correct = CorrectMedicationHistoryFactUseCase(
        record_repository=fixture.record_repository,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=lock,
        staff_qualification=fixture.staff_qualification,
        counselor_service=CounselorQualificationService(),
        category_catalog_repository=fixture.category_catalog_repository,
        store_operations=fixture.store_operations,
        clock=fixture.clock,
        projection_service=projection_service,
    )
    await use_case_correct.execute(
        CorrectMedicationHistoryFactCommand(
            corporate_id=str(fixture.corporate_id.value),
            record_id=str(record.id.value),
            target="method",
            operation="replace",
            reason="事実訂正",
            value="face_to_face",
        )
    )
    assert (fixture.corporate_id, fixture.patient_id) in projection_service.calls

    # 3. 手動再構築
    projection_service.calls.clear()
    use_case_rebuild = RebuildPatientMedicalProfileUseCase(
        record_repository=fixture.record_repository,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=NullUnitOfWork(),
        organization_lock=lock,
        projection_service=projection_service,
    )
    await use_case_rebuild.execute(
        RebuildPatientMedicalProfileCommand(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            as_of=datetime(2026, 9, 21, tzinfo=UTC).date(),
        )
    )
    assert (fixture.corporate_id, fixture.patient_id) in projection_service.calls


@pytest.mark.asyncio
async def test_共通ProjectionServiceは複数店舗の対象選別と既存ID維持を行う() -> None:
    """共通サービスが全店舗の確定記録を集め、未確定を除外し、既存頭書きIDを維持して保存する。"""
    repo = InMemoryMedicationHistoryRepository()
    profile_repo = InMemoryPatientMedicalProfileRepository()
    service = PatientMedicalProfileProjectionService(repo, profile_repo)

    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    store_a = StoreId.generate()
    store_b = StoreId.generate()

    # 店舗Aの確定記録（アレルギーあり）
    record_a = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            store_id=store_a,
            patient_id=patient_id,
            counseled_at=datetime(2026, 9, 10, 4, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン"),)
            ),
        )
    )
    # 店舗Bの未確定下書き（除外されるべき）
    draft_b = create_record(
        corporate_id=corporate_id,
        store_id=store_b,
        patient_id=patient_id,
        counseled_at=datetime(2026, 9, 15, 4, tzinfo=UTC),
        profile_updates=ProfileUpdateIntents(
            new_allergies=(create_allergy_intent(allergen="誤った下書きアレルゲン"),)
        ),
    )
    # 店舗Bの確定記録（副作用あり）
    record_b = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            store_id=store_b,
            patient_id=patient_id,
            counseled_at=datetime(2026, 9, 20, 4, tzinfo=UTC),
        )
    )
    await repo.save(record_a)
    await repo.save(draft_b)
    await repo.save(record_b)

    # 初回投影
    first_profile = await service.project(
        corporate_id=corporate_id, patient_id=patient_id
    )
    assert first_profile is not None
    assert len(first_profile.allergies) == 1
    assert first_profile.allergies[0].allergen.value == "ペニシリン"
    assert "誤った下書きアレルゲン" not in [
        a.allergen.value for a in first_profile.allergies
    ]

    # 2回目の再投影で同一IDが維持される
    second_profile = await service.project(
        corporate_id=corporate_id, patient_id=patient_id
    )
    assert second_profile.id == first_profile.id


@pytest.mark.asyncio
async def test_手動再構築もUnitOfWorkの有効性を検査する() -> None:
    """開始されていないUnit of Workを渡された手動再構築は拒否される。"""
    fixture = create_fixture()
    use_case = RebuildPatientMedicalProfileUseCase(
        record_repository=fixture.record_repository,
        profile_repository=fixture.profile_repository,
        corporate_access=fixture.corporate_access,
        unit_of_work=_InactiveUnitOfWork(),
        organization_lock=FakeOrganizationLock(),
    )
    with pytest.raises(ApplicationError, match="トランザクションが開始されていません"):
        await use_case.execute(
            RebuildPatientMedicalProfileCommand(
                corporate_id=str(fixture.corporate_id.value),
                patient_id=str(fixture.patient_id.value),
                as_of=datetime(2026, 9, 20, tzinfo=UTC).date(),
            )
        )
