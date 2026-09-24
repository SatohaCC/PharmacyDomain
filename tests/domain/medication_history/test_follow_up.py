"""服薬期間中のフォローアップ（調剤後フォロー記録）のドメインテスト。"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import (
    DuplicatedFollowUpIdError,
    FollowUpDateBeforeCounselingError,
    FollowUpOnDraftError,
    ProfilePatientMismatchError,
    SoapContentRequiredError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    ConditionStatus,
    CounselingMethod,
    CounselingNote,
    MajorCategoryCode,
    MediumCategoryCode,
    StatutoryCategory,
)
from app.domain.medication_history.value_objects import (
    CategorizedNote,
    LabeledNote,
    SoapRecord,
)
from app.domain.patient.primitives import PatientId
from app.domain.shared.medicine import MedicineName
from app.domain.staff.primitives import StaffId
from tests.factories.medication_history_factory import (
    COUNSELED_AT,
    create_adverse_reaction_intent,
    create_allergy_intent,
    create_condition_intent,
    create_follow_up,
    create_record,
    create_update_condition_status_intent,
)


def _finalized_record(**kwargs: Any) -> MedicationHistoryRecord:
    record = create_record(**kwargs)
    return record.finalize()


class TestFollowUpRecordDomain:
    """フォローアップ記録および薬歴集約の不変条件テスト。"""

    def test_add_follow_up_to_finalized_record(self) -> None:
        """TC-FOL-01: 確定済み薬歴に完全なフォローアップ記録を追加できる（不変性の維持）。"""
        record = _finalized_record()
        follow_up = create_follow_up(
            followed_up_at=COUNSELED_AT + timedelta(days=3),
            method=CounselingMethod.TELEPHONE,
        )

        updated = record.add_follow_up(follow_up)

        assert len(updated.follow_ups) == 1
        assert updated.follow_ups[0].id == follow_up.id
        assert updated.follow_ups[0].method == CounselingMethod.TELEPHONE
        assert len(record.follow_ups) == 0  # 元のインスタンスは不変

    def test_add_multiple_follow_ups(self) -> None:
        """TC-FOL-02: 確定済み薬歴に複数回（0..N件）のフォローアップを追加できる。"""
        record = _finalized_record()
        fu1 = create_follow_up(followed_up_at=COUNSELED_AT + timedelta(days=3))
        fu2 = create_follow_up(followed_up_at=COUNSELED_AT + timedelta(days=7))

        updated = record.add_follow_up(fu1).add_follow_up(fu2)

        assert len(updated.follow_ups) == 2
        assert updated.follow_ups[0].id == fu1.id
        assert updated.follow_ups[1].id == fu2.id

    def test_add_follow_up_with_partial_content(self) -> None:
        """TC-FOL-03: S節のみ、または追加区分メモのみのフォローアップでも登録できる。"""
        record = _finalized_record()

        # S節のみのSOAP
        soap_s_only = SoapRecord(
            subjective=(
                LabeledNote(
                    text=CounselingNote("電話にて体調良好と確認。"),
                    category=StatutoryCategory.GENERAL,
                ),
            )
        )
        fu_soap = create_follow_up(
            followed_up_at=COUNSELED_AT + timedelta(days=2), soap=soap_s_only
        )
        updated1 = record.add_follow_up(fu_soap)
        assert len(updated1.follow_ups) == 1

        # SOAP空だが追加区分メモがある場合
        fu_note = create_follow_up(
            followed_up_at=COUNSELED_AT + timedelta(days=4),
            soap=SoapRecord(),
            additional_notes=(
                CategorizedNote(
                    major_category_code=MajorCategoryCode("followup"),
                    medium_category_code=MediumCategoryCode("adherence_check"),
                    text=CounselingNote("残薬なし、服用継続中。"),
                ),
            ),
        )
        updated2 = record.add_follow_up(fu_note)
        assert len(updated2.follow_ups) == 1

    def test_cannot_add_follow_up_to_draft_record(self) -> None:
        """TC-FOL-04: 下書き状態（DRAFT）の薬歴へのフォローアップ追加は拒否される。"""
        draft_record = create_record()  # 未確定（DRAFT）
        follow_up = create_follow_up(followed_up_at=COUNSELED_AT + timedelta(days=1))

        with pytest.raises(FollowUpOnDraftError):
            draft_record.add_follow_up(follow_up)

    def test_cannot_add_follow_up_before_counseling_date(self) -> None:
        """TC-FOL-05: 初回服薬指導日時より過去の日時のフォローアップは拒否される。"""
        record = _finalized_record(counseled_at=COUNSELED_AT)
        past_follow_up = create_follow_up(
            followed_up_at=COUNSELED_AT - timedelta(hours=1)
        )

        with pytest.raises(FollowUpDateBeforeCounselingError):
            record.add_follow_up(past_follow_up)

    def test_cannot_add_duplicate_follow_up_id(self) -> None:
        """TC-FOL-06: 重複するFollowUpIdの追加は拒否される。"""
        record = _finalized_record()
        follow_up = create_follow_up(followed_up_at=COUNSELED_AT + timedelta(days=2))
        updated = record.add_follow_up(follow_up)

        with pytest.raises(DuplicatedFollowUpIdError):
            updated.add_follow_up(follow_up)

    def test_blank_follow_up_rejected(self) -> None:
        """TC-FOL-07: SOAPも追加メモも空である白紙のフォローアップは拒否される。"""
        with pytest.raises(SoapContentRequiredError):
            create_follow_up(
                soap=SoapRecord(),
                additional_notes=(),
            )

    def test_counseling_method_otc(self) -> None:
        """TC-FOL-08: CounselingMethod.OTCが正しく定義され使用できる。"""
        assert CounselingMethod.OTC.value == "otc"
        assert CounselingMethod.OTC.label == "OTC対応"

        fu = create_follow_up(method=CounselingMethod.OTC)
        assert fu.method == CounselingMethod.OTC


class TestFollowUpPatientProfileProjection:
    """フォローアップによる頭書き投影および再構築テスト。"""

    def test_apply_follow_up_projects_adverse_reactions(self) -> None:
        """TC-PRF-01: フォローアップ由来の副作用歴が頭書きに反映され、実施日・指導者が記録される。"""
        record = _finalized_record()
        counselor = StaffId.generate()
        follow_up_date = datetime(2026, 8, 28, 6, 0, tzinfo=UTC)

        from app.domain.medication_history.value_objects import ProfileUpdateIntents

        profile_updates = ProfileUpdateIntents(
            new_adverse_reactions=(
                create_adverse_reaction_intent(
                    medicine_name="ロキソプロフェンＮａ錠６０ｍｇ",
                    symptom="胃部不快感",
                ),
            )
        )
        follow_up = create_follow_up(
            counselor_id=counselor,
            followed_up_at=follow_up_date,
            profile_updates=profile_updates,
        )

        profile = PatientMedicalProfile.empty_for(
            corporate_id=record.corporate_id, patient_id=record.patient_id
        ).apply(record)

        updated_profile = profile.apply_follow_up(record, follow_up)

        assert len(updated_profile.adverse_reactions) == 1
        adv = updated_profile.adverse_reactions[0]
        assert adv.medicine_name == MedicineName("ロキソプロフェンＮａ錠６０ｍｇ")
        assert adv.provenance.source_record_id == record.id
        assert adv.provenance.recorded_by == counselor
        assert adv.provenance.recorded_on == follow_up_date.date()

    def test_apply_follow_up_updates_condition_status(self) -> None:
        """TC-PRF-02: フォローアップで既往症状態を更新し、頭書きに反映される。"""
        # 初回指導で緑内障を登録
        from app.domain.medication_history.value_objects import ProfileUpdateIntents

        initial_intents = ProfileUpdateIntents(
            new_conditions=(create_condition_intent(condition_name="緑内障"),)
        )
        record = _finalized_record(profile_updates=initial_intents)
        profile = PatientMedicalProfile.empty_for(
            corporate_id=record.corporate_id, patient_id=record.patient_id
        ).apply(record)

        # フォローアップで治癒（RESOLVED）に更新
        follow_up_counselor = StaffId.generate()
        follow_up_intents = ProfileUpdateIntents(
            updated_conditions=(
                create_update_condition_status_intent(
                    condition_name="緑内障",
                    new_status=ConditionStatus.RESOLVED,
                ),
            )
        )
        follow_up = create_follow_up(
            counselor_id=follow_up_counselor,
            followed_up_at=COUNSELED_AT + timedelta(days=5),
            profile_updates=follow_up_intents,
        )

        updated_profile = profile.apply_follow_up(record, follow_up)

        assert len(updated_profile.medical_conditions) == 1
        cond = updated_profile.medical_conditions[0]
        assert cond.condition_status == ConditionStatus.RESOLVED
        assert cond.provenance.recorded_by == follow_up_counselor

    def test_rebuild_profile_includes_follow_ups_in_chronological_order(self) -> None:
        """TC-PRF-03: rebuild_from が初回指導と各フォローアップを時系列順に畳み込んで頭書きを再現する。"""
        from app.domain.medication_history.value_objects import ProfileUpdateIntents

        corp_id = CorporateId.generate()
        pat_id = PatientId.generate()

        # 薬歴1: T1 (8/20) に既往症「気管支喘息」を登録
        t1 = datetime(2026, 8, 20, 5, 0, tzinfo=UTC)
        r1 = _finalized_record(
            corporate_id=corp_id,
            patient_id=pat_id,
            counseled_at=t1,
            profile_updates=ProfileUpdateIntents(
                new_conditions=(create_condition_intent(condition_name="気管支喘息"),)
            ),
        )

        # 薬歴1のフォローアップ: T2 (8/23) にアレルギー「ペニシリン系」を追加
        t2 = datetime(2026, 8, 23, 5, 0, tzinfo=UTC)
        fu1 = create_follow_up(
            followed_up_at=t2,
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(allergen="ペニシリン系"),)
            ),
        )
        r1_with_fu = r1.add_follow_up(fu1)

        # 薬歴2: T3 (8/25) に副作用「胃部不快感」を追加
        t3 = datetime(2026, 8, 25, 5, 0, tzinfo=UTC)
        r2 = _finalized_record(
            corporate_id=corp_id,
            patient_id=pat_id,
            counseled_at=t3,
            profile_updates=ProfileUpdateIntents(
                new_adverse_reactions=(
                    create_adverse_reaction_intent(
                        medicine_name="ロキソプロフェンＮａ錠６０ｍｇ",
                        symptom="胃部不快感",
                    ),
                )
            ),
        )

        # 薬歴2のフォローアップ: T4 (8/28) に「気管支喘息」を治癒に更新
        t4 = datetime(2026, 8, 28, 5, 0, tzinfo=UTC)
        fu2 = create_follow_up(
            followed_up_at=t4,
            profile_updates=ProfileUpdateIntents(
                updated_conditions=(
                    create_update_condition_status_intent(
                        condition_name="気管支喘息",
                        new_status=ConditionStatus.RESOLVED,
                    ),
                )
            ),
        )
        r2_with_fu = r2.add_follow_up(fu2)

        # 順序をシャッフルして rebuild_from に渡す
        rebuilt = PatientMedicalProfile.rebuild_from(
            corporate_id=corp_id,
            patient_id=pat_id,
            records=(r2_with_fu, r1_with_fu),
        )

        assert len(rebuilt.allergies) == 1
        assert len(rebuilt.adverse_reactions) == 1
        assert len(rebuilt.medical_conditions) == 1
        assert (
            rebuilt.medical_conditions[0].condition_status == ConditionStatus.RESOLVED
        )

    def test_apply_follow_up_rejects_patient_mismatch(self) -> None:
        """TC-PRF-04: 別患者の薬歴・フォローアップの投影は拒否される。"""
        record = _finalized_record()
        follow_up = create_follow_up(followed_up_at=COUNSELED_AT + timedelta(days=1))
        other_profile = PatientMedicalProfile.empty_for(
            corporate_id=record.corporate_id,
            patient_id=PatientId.generate(),  # 別患者
        )

        with pytest.raises(ProfilePatientMismatchError):
            other_profile.apply_follow_up(record, follow_up)
