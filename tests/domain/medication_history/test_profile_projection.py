"""頭書きが薬歴からの投影であることを、実行可能な形で固定する。

頭書きは薬歴の列から決定的に再構築できなければならない。
ここで**逐次適用の結果と一括再構築の結果が一致すること**を要求する。

この一致が保てるのは、頭書きの状態変更が ``apply(record)`` だけだからである。
薬歴に由来しない直接編集メソッド（``register_allergy(...)`` など）を公開すると
このファイルのテストが落ちる。
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    ConcurrentMedicationNotFoundError,
    GenericPreferenceType,
    PatientMedicalProfile,
    ProfilePatientMismatchError,
    ProfileUpdateIntents,
    UnfinalizedRecordProjectionError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.patient.primitives import PatientId
from tests.factories.medication_history_factory import (
    create_adverse_reaction_intent,
    create_allergy_intent,
    create_concurrent_intent,
    create_condition_intent,
    create_generic_preference_intents,
    create_lifestyle_intents,
    create_record,
    create_stop_intent,
)

_CORPORATE_ID = CorporateId.generate()
_PATIENT_ID = PatientId.generate()


def _record(
    *,
    counseled_at: datetime,
    profile_updates: ProfileUpdateIntents,
    corporate_id: CorporateId = _CORPORATE_ID,
    patient_id: PatientId = _PATIENT_ID,
) -> MedicationHistoryRecord:
    """確定済の薬歴を1件組み立てる。"""
    return create_record(
        corporate_id=corporate_id,
        patient_id=patient_id,
        counseled_at=counseled_at,
        profile_updates=profile_updates,
    ).finalize()


def _timeline() -> tuple[MedicationHistoryRecord, ...]:
    """頭書きのすべての要素に触る薬歴の列を、時系列で組み立てる。"""
    return (
        _record(
            counseled_at=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(),),
                new_conditions=(create_condition_intent(),),
            ),
        ),
        _record(
            counseled_at=datetime(2026, 7, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                new_adverse_reactions=(create_adverse_reaction_intent(),),
                new_concurrent_medications=(create_concurrent_intent(),),
            ),
        ),
        _record(
            counseled_at=datetime(2026, 8, 1, 1, 0, tzinfo=UTC),
            profile_updates=create_lifestyle_intents(),
        ),
        _record(
            counseled_at=datetime(2026, 8, 24, 1, 0, tzinfo=UTC),
            profile_updates=create_generic_preference_intents(),
        ),
        _record(
            counseled_at=datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                stopped_concurrent_medications=(create_stop_intent(),),
            ),
        ),
    )


def _apply_sequentially(
    records: tuple[MedicationHistoryRecord, ...],
) -> PatientMedicalProfile:
    """薬歴を1件ずつ適用して頭書きを作る（日々の運用と同じ経路）。"""
    profile = PatientMedicalProfile.empty_for(
        corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID
    )
    for record in records:
        profile = profile.apply(record)
    return profile


def _content_of(profile: PatientMedicalProfile) -> tuple[object, ...]:
    """同一性（``id``）を除いた頭書きの中身を比較用に取り出す。

    集約ルートは ``eq=False`` で同一性比較になるため、``==`` では中身を比べられない。
    """
    return (
        profile.corporate_id,
        profile.patient_id,
        profile.allergies,
        profile.adverse_reactions,
        profile.medical_conditions,
        profile.concurrent_medications,
        profile.lifestyle,
        profile.generic_preference,
        profile.family_pharmacist,
    )


class Test再構築の一致:
    """頭書きを薬歴から回復できることを検証する。"""

    def test_逐次適用と一括再構築の結果が_一致する(self) -> None:
        """``save(profile)`` が失敗しても薬歴から回復できることの根拠。"""
        # Arrange
        records = _timeline()

        # Act
        sequential = _apply_sequentially(records)
        rebuilt = PatientMedicalProfile.rebuild_from(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID, records=records
        )

        # Assert
        assert _content_of(rebuilt) == _content_of(sequential)

    def test_薬歴の並び順が変わっても_再構築の結果は同じ(self) -> None:
        """再構築は ``counseled_at`` 昇順に畳み込む。入力順に依存しない。"""
        # Arrange
        records = _timeline()

        # Act
        in_order = PatientMedicalProfile.rebuild_from(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID, records=records
        )
        shuffled = PatientMedicalProfile.rebuild_from(
            corporate_id=_CORPORATE_ID,
            patient_id=_PATIENT_ID,
            records=tuple(reversed(records)),
        )

        # Assert
        assert _content_of(shuffled) == _content_of(in_order)

    def test_同じ薬歴列からは_何度でも同じ頭書きが得られる(self) -> None:
        # Arrange
        records = _timeline()

        # Act
        first = PatientMedicalProfile.rebuild_from(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID, records=records
        )
        second = PatientMedicalProfile.rebuild_from(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID, records=records
        )

        # Assert
        assert _content_of(first) == _content_of(second)


class Test由来:
    """すべての要素が薬歴に由来する。"""

    def test_すべての要素に_由来の薬歴IDが刻まれる(self) -> None:
        # Arrange
        records = _timeline()

        # Act
        profile = _apply_sequentially(records)

        # Assert
        record_ids = {str(record.id.value) for record in records}
        assert set(profile.source_record_ids) <= record_ids
        assert profile.source_record_ids

    def test_由来は_投影時刻ではなく指導時刻から作られる(self) -> None:
        """監査で「誰がいつ登録したか」を示すのは指導の事実であるため。"""
        # Arrange: 月初以外の日にすることで「日付を捨てる」実装を落とせるようにする
        record = _record(
            counseled_at=datetime(2026, 6, 15, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                new_allergies=(create_allergy_intent(),)
            ),
        )

        # Act
        profile = _apply_sequentially((record,))

        # Assert
        provenance = profile.allergies[0].provenance
        assert provenance.recorded_on == date(2026, 6, 15)
        assert provenance.recorded_by == record.counselor_id
        assert provenance.source_record_id == record.id

    def test_頭書きの状態変更は_applyだけである(self) -> None:
        """薬歴に由来しない直接編集メソッドを足すと、ここで落ちる。

        再構築の一致（``Test再構築の一致``）はこの制約の上にしか成り立たない。
        """
        # Arrange
        forbidden = {
            "register_allergy",
            "register_adverse_reaction",
            "register_medical_condition",
            "add_concurrent_medication",
            "stop_concurrent_medication",
            "update_lifestyle",
            "update_generic_preference",
            "assign_family_pharmacist",
        }

        # Act
        public_methods = {
            name for name in dir(PatientMedicalProfile) if not name.startswith("_")
        }

        # Assert
        assert not forbidden & public_methods
        assert "apply" in public_methods


class Test投影の前提:
    """壊れた入力を投影させない。"""

    def test_未確定の薬歴は_投影できない(self) -> None:
        """下書きは以降も書き換わるため、投影の入力にすると結果が安定しない。"""
        # Arrange
        draft = create_record(corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID)
        profile = PatientMedicalProfile.empty_for(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID
        )

        # Act / Assert
        with pytest.raises(UnfinalizedRecordProjectionError):
            profile.apply(draft)

    def test_別患者の薬歴は_投影できない(self) -> None:
        # Arrange
        other = _record(
            counseled_at=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(),
            patient_id=PatientId.generate(),
        )
        profile = PatientMedicalProfile.empty_for(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID
        )

        # Act / Assert
        with pytest.raises(ProfilePatientMismatchError):
            profile.apply(other)

    def test_別法人の薬歴は_投影できない(self) -> None:
        # Arrange
        other = _record(
            counseled_at=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(),
            corporate_id=CorporateId.generate(),
        )
        profile = PatientMedicalProfile.empty_for(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID
        )

        # Act / Assert
        with pytest.raises(ProfilePatientMismatchError):
            profile.apply(other)

    def test_存在しない併用薬は_終了させられない(self) -> None:
        # Arrange
        record = _record(
            counseled_at=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                stopped_concurrent_medications=(create_stop_intent(),)
            ),
        )
        profile = PatientMedicalProfile.empty_for(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID
        )

        # Act / Assert
        with pytest.raises(ConcurrentMedicationNotFoundError, match="総合感冒薬"):
            profile.apply(record)


class Test併用薬の期間:
    """``is_active`` を持たず ``ended_on`` から導出する。"""

    def test_開始日から_併用しているとみなす(self) -> None:
        """開始日は含む。前日は含まない。"""
        # Arrange: 併用薬の開始日は 2026-08-01、終了はまだ記録していない
        profile = _apply_sequentially(_timeline()[:2])

        # Act / Assert
        assert profile.active_concurrent_medications(date(2026, 7, 31)) == ()
        assert profile.active_concurrent_medications(date(2026, 8, 1)) != ()
        assert profile.active_concurrent_medications(date(2026, 12, 31)) != ()

    def test_終了日を含む日までは_併用している(self) -> None:
        """終了日を含む閉区間で判定する。"""
        # Arrange
        profile = _apply_sequentially(_timeline())

        # Act / Assert
        assert profile.active_concurrent_medications(date(2026, 8, 20)) != ()
        assert profile.active_concurrent_medications(date(2026, 8, 21)) == ()

    def test_遡って過去のある日の併用状況を判定できる(self) -> None:
        """相互作用チェックで実際に要る。``date.today()`` では表現できない。"""
        # Arrange
        profile = _apply_sequentially(_timeline())

        # Act
        past = profile.active_concurrent_medications(date(2026, 8, 10))

        # Assert
        assert len(past) == 1
        assert past[0].ended_on == date(2026, 8, 20)


class Test禁忌と意向:
    """画面で使う導出。"""

    def test_禁忌対象の疾患だけを取り出せる(self) -> None:
        # Arrange
        record = _record(
            counseled_at=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
            profile_updates=ProfileUpdateIntents(
                new_conditions=(
                    create_condition_intent("緑内障", is_contraindication_target=True),
                    create_condition_intent(
                        "季節性アレルギー性鼻炎", is_contraindication_target=False
                    ),
                )
            ),
        )

        # Act
        profile = _apply_sequentially((record,))

        # Assert
        assert len(profile.medical_conditions) == 2
        assert len(profile.contraindication_conditions) == 1
        assert profile.contraindication_conditions[0].condition_name.value == "緑内障"

    def test_後発医薬品の意向は_最後の記録で上書きされる(self) -> None:
        """意向は履歴ではなく現在値。過去の意向は薬歴側に残る。"""
        # Arrange
        records = (
            _record(
                counseled_at=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),
                profile_updates=create_generic_preference_intents(
                    GenericPreferenceType.REFUSES
                ),
            ),
            _record(
                counseled_at=datetime(2026, 8, 1, 1, 0, tzinfo=UTC),
                profile_updates=create_generic_preference_intents(
                    GenericPreferenceType.ACCEPTS
                ),
            ),
        )

        # Act
        profile = PatientMedicalProfile.rebuild_from(
            corporate_id=_CORPORATE_ID, patient_id=_PATIENT_ID, records=records
        )

        # Assert
        assert profile.generic_preference is not None
        assert profile.generic_preference.preference is GenericPreferenceType.ACCEPTS
