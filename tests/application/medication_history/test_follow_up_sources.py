"""店舗横断候補の絞り込み・認可・情報最小化を検証する。"""

from dataclasses import fields

import pytest

from app.application.access_control.exceptions import TenantBoundaryNotFoundError
from app.application.access_control.models import ActorRole
from app.application.common.exceptions import AuthorizationError
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history.get_follow_up_sources import (
    FollowUpSourceDto,
    GetFollowUpSourcesQuery,
    GetFollowUpSourcesUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import StoreId
from tests.application.medication_history.helpers import (
    MedicationHistoryFixture,
    create_fixture,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_independent_follow_up_record,
    create_record,
    finalize_record_with_review,
)


def _use_case(fixture: MedicationHistoryFixture) -> GetFollowUpSourcesUseCase:
    """テストFixtureの境界を候補取得UseCaseへ接続する。"""
    return GetFollowUpSourcesUseCase(
        source_boundary=fixture.follow_up_source_boundary,
        corporate_access=fixture.corporate_access,
        store_operations=fixture.store_operations,
    )


async def _seed_chain(fixture: MedicationHistoryFixture) -> tuple[str, str]:
    """初回と独立フォローアップの確定済記録をRepositoryへ保存する。"""
    initial = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            dispensing_id=fixture.dispensing.id,
            prescription_id=fixture.dispensing.prescription_id,
        )
    )
    follow_up = create_independent_follow_up_record(
        initial,
        store_id=StoreId.generate(),
        counseled_at=COUNSELED_AT.replace(day=27),
        finalized=True,
    )
    await fixture.record_repository.save(initial)
    await fixture.record_repository.save(follow_up)
    return str(initial.id.value), str(follow_up.id.value)


async def test_tc22_候補は指定患者の確定済み薬歴だけを連鎖順に返す() -> None:
    fixture = create_fixture()
    initial_id, follow_up_id = await _seed_chain(fixture)
    draft = create_record(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
    )
    other_patient = finalize_record_with_review(
        create_record(corporate_id=fixture.corporate_id, store_id=fixture.store_id)
    )
    other_corporate = finalize_record_with_review(
        create_record(corporate_id=CorporateId.generate(), store_id=StoreId.generate())
    )
    await fixture.record_repository.save(draft)
    await fixture.record_repository.save(other_patient)
    await fixture.record_repository.save(other_corporate)

    candidates = await _use_case(fixture).execute(
        GetFollowUpSourcesQuery(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            store_id=str(fixture.store_id.value),
        )
    )

    assert {item.record_id for item in candidates} == {initial_id, follow_up_id}
    assert candidates[0].record_id == follow_up_id
    assert candidates[0].source_record_id == initial_id


async def test_tc23_候補DTOに薬歴本文や頭書き差分を含めない() -> None:
    fixture = create_fixture()
    await _seed_chain(fixture)

    candidates = await _use_case(fixture).execute(
        GetFollowUpSourcesQuery(
            corporate_id=str(fixture.corporate_id.value),
            patient_id=str(fixture.patient_id.value),
            store_id=str(fixture.store_id.value),
        )
    )

    assert candidates
    allowed = {
        "record_id",
        "record_kind",
        "source_record_id",
        "store_id",
        "dispensing_id",
        "prescription_id",
        "counseled_at",
    }
    assert {field.name for field in fields(FollowUpSourceDto)} == allowed
    assert not hasattr(candidates[0], "soap")
    assert not hasattr(candidates[0], "profile_updates")


async def test_tc24_候補取得は店舗権限と法人状態を参照検索前に検証する() -> None:
    operator = create_fixture(store_role=ActorRole.STORE_OPERATOR)
    await _seed_chain(operator)
    target_store = StoreId.generate()
    before_list = operator.follow_up_source_boundary.list_calls
    query = GetFollowUpSourcesQuery(
        corporate_id=str(operator.corporate_id.value),
        patient_id=str(operator.patient_id.value),
        store_id=str(target_store.value),
    )

    with pytest.raises(TenantBoundaryNotFoundError):
        await _use_case(operator).execute(query)
    assert operator.follow_up_source_boundary.list_calls == before_list

    viewer = create_fixture(store_role=ActorRole.STORE_VIEWER)
    with pytest.raises(AuthorizationError):
        await _use_case(viewer).execute(
            GetFollowUpSourcesQuery(
                corporate_id=str(viewer.corporate_id.value),
                patient_id=str(viewer.patient_id.value),
                store_id=str(viewer.store_id.value),
            )
        )
    assert viewer.follow_up_source_boundary.list_calls == 0

    inactive = create_fixture()
    inactive.corporate_repository.set_inactive(inactive.corporate_id)
    with pytest.raises(CorporateInactiveError):
        await _use_case(inactive).execute(
            GetFollowUpSourcesQuery(
                corporate_id=str(inactive.corporate_id.value),
                patient_id=str(inactive.patient_id.value),
                store_id=str(inactive.store_id.value),
            )
        )
    assert inactive.follow_up_source_boundary.list_calls == 0
