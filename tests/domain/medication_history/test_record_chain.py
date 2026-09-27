"""Eventと薬歴の1対1参照および移行記録の性質を検証する。"""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.domain.care_event.primitives import EventId
from app.domain.medication_history.exceptions import (
    MedicationHistoryAlreadyFinalizedError,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    FollowUpRecordedTimestamp,
    GenericPreferenceType,
    MedicationHistoryStatus,
)
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_generic_preference_intents,
    create_record,
)


def test_tc45_21_Event薬歴は薬歴用調剤情報なしで作成できる() -> None:
    event_id = EventId.generate()

    record = replace(
        create_record(),
        event_id=event_id,
        dispensing_id=None,
        prescription_id=None,
    )

    assert record.event_id == event_id
    assert record.dispensing_id is None
    assert record.prescription_id is None


def test_tc45_50_旧子要素から移行した記録は確定監査値なしで頭書きへ投影できる() -> None:
    recorded_at = COUNSELED_AT + timedelta(days=4)
    legacy_record = replace(
        create_record(
            profile_updates=create_generic_preference_intents(
                GenericPreferenceType.REFUSES
            )
        ),
        status=MedicationHistoryStatus.LEGACY_RECORDED,
        recorded_at=FollowUpRecordedTimestamp(recorded_at),
    )

    profile = PatientMedicalProfile.rebuild_from(
        corporate_id=legacy_record.corporate_id,
        patient_id=legacy_record.patient_id,
        records=(legacy_record,),
    )

    assert legacy_record.is_projection_eligible
    assert not legacy_record.is_finalized
    assert legacy_record.finalized_at is None
    assert profile.generic_preference is not None
    assert profile.generic_preference.preference is GenericPreferenceType.REFUSES
    assert profile.generic_preference.provenance.source_record_id == legacy_record.id


def test_tc45_50_移行記録を通常の下書き更新や確定に使えない() -> None:
    legacy_record = replace(
        create_record(),
        status=MedicationHistoryStatus.LEGACY_RECORDED,
    )

    with pytest.raises(MedicationHistoryAlreadyFinalizedError):
        legacy_record.update_draft_soap(legacy_record.soap)
    with pytest.raises(MedicationHistoryAlreadyFinalizedError):
        legacy_record.finalize(
            finalized_at=legacy_record.finalized_at,
            finalized_by=legacy_record.recorded_by,
        )
