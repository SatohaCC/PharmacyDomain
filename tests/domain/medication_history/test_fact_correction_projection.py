"""事実訂正後の薬歴列から医療プロファイルを再生する。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    CounselingTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
    GenericPreferenceType,
)
from app.domain.medication_history.value_objects import ProfileUpdateIntents
from app.domain.patient.primitives import PatientId
from app.domain.staff.primitives import StaffId
from tests.domain.medication_history.test_fact_correction import (
    _correct,
    _element_id,
)
from tests.factories.medication_history_factory import (
    create_allergy_intent,
    create_generic_preference_intents,
    create_record,
    finalize_record_with_review,
)

_DAY_ONE = datetime(2026, 8, 20, 3, tzinfo=UTC)


def test_tc15_同名の別薬歴Intentを巻き込まず1件だけ取り消す() -> None:
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    updates = ProfileUpdateIntents(new_allergies=(create_allergy_intent(),))
    first = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            patient_id=patient_id,
            counseled_at=_DAY_ONE,
            profile_updates=updates,
        )
    )
    second = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            patient_id=patient_id,
            counseled_at=_DAY_ONE + timedelta(days=1),
            profile_updates=updates,
        )
    )
    target = _element_id(first, "profile_updates.new_allergies", 0)

    corrected = _correct(first, target=target, operation="retract")
    rebuilt = PatientMedicalProfile.rebuild_from(
        corporate_id=corporate_id,
        patient_id=patient_id,
        records=(second, corrected),
    )

    assert len(rebuilt.allergies) == 1
    assert rebuilt.allergies[0].provenance.source_record_id == second.id
    assert first.profile_updates.new_allergies == updates.new_allergies


def test_tc26_訂正後の指導日時で全薬歴の再生順序が変わる() -> None:
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    first = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            patient_id=patient_id,
            counseled_at=_DAY_ONE,
            profile_updates=create_generic_preference_intents(
                GenericPreferenceType.ACCEPTS
            ),
        ),
        finalized_at=FinalizedTimestamp(_DAY_ONE + timedelta(days=3)),
        delay_reason=FinalizationDelayReason("後日に記録を確定した。"),
    )
    second = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            patient_id=patient_id,
            counseled_at=_DAY_ONE + timedelta(days=1),
            profile_updates=create_generic_preference_intents(
                GenericPreferenceType.REFUSES
            ),
        )
    )

    corrected = _correct(
        first,
        target="counseled_at",
        value=CounselingTimestamp(_DAY_ONE + timedelta(days=2)),
    )
    in_order = PatientMedicalProfile.rebuild_from(
        corporate_id=corporate_id,
        patient_id=patient_id,
        records=(corrected, second),
    )
    reversed_order = PatientMedicalProfile.rebuild_from(
        corporate_id=corporate_id,
        patient_id=patient_id,
        records=(second, corrected),
    )

    assert in_order.generic_preference is not None
    assert reversed_order.generic_preference is not None
    assert in_order.generic_preference.preference is GenericPreferenceType.ACCEPTS
    assert reversed_order.generic_preference == in_order.generic_preference
    assert in_order.generic_preference.provenance.source_record_id == first.id


def test_tc27_指導者と日時の訂正がプロフィールの由来へ反映される() -> None:
    corporate_id = CorporateId.generate()
    patient_id = PatientId.generate()
    original = finalize_record_with_review(
        create_record(
            corporate_id=corporate_id,
            patient_id=patient_id,
            counseled_at=_DAY_ONE,
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(),)
            ),
        ),
        finalized_at=FinalizedTimestamp(_DAY_ONE + timedelta(days=3)),
        delay_reason=FinalizationDelayReason("後日に記録を確定した。"),
    )
    actual_counselor = StaffId.generate()
    actual_time = CounselingTimestamp(_DAY_ONE + timedelta(days=1))

    with_counselor = _correct(original, target="counselor_id", value=actual_counselor)
    corrected = _correct(with_counselor, target="counseled_at", value=actual_time)
    rebuilt = PatientMedicalProfile.rebuild_from(
        corporate_id=corporate_id,
        patient_id=patient_id,
        records=(corrected,),
    )

    assert len(rebuilt.allergies) == 1
    provenance = rebuilt.allergies[0].provenance
    assert provenance.recorded_by == actual_counselor
    assert provenance.recorded_on == actual_time.value.date()
    assert original.counselor_id != actual_counselor
    assert original.counseled_at != actual_time
