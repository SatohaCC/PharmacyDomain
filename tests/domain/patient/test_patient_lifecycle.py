"""患者集約のライフサイクル状態遷移・不変条件・名寄せマージのテスト。"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.patient.exceptions import PatientStateConflictError
from app.domain.patient.lifecycle import (
    PatientStatus,
    PatientStatusChange,
    PatientStatusReason,
)
from app.domain.patient.merge_service import PatientMergeService
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import (
    PatientBirthDate,
    PatientId,
    PatientNumber,
)
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import PersonNames


def _create_patient(
    *,
    corporate_id: CorporateId | None = None,
    patient_number: int = 1,
) -> Patient:
    return Patient.create(
        corporate_id=corporate_id or CorporateId.generate(),
        names=PersonNames.create(
            last_name="山田",
            first_name="太郎",
            last_name_kana="ヤマダ",
            first_name_kana="タロウ",
        ),
        patient_number=PatientNumber(patient_number),
        birth_date=PatientBirthDate(date(1990, 1, 1)),
    )


def _actor_context() -> tuple[AccountPersonId, UserAccountId, datetime]:
    return (
        AccountPersonId.generate(),
        UserAccountId.generate(),
        datetime.now(UTC),
    )


# ==============================================================================
# TC-02 〜 TC-04: プリミティブ・値オブジェクト
# ==============================================================================


def test_TC02_患者状態列挙型の定義() -> None:
    assert PatientStatus.ACTIVE.value == "active"
    assert PatientStatus.INACTIVE.value == "inactive"
    assert PatientStatus.MERGED.value == "merged"
    assert len(PatientStatus) == 3


def test_TC03_患者状態変更理由のバリデーション() -> None:
    # 正常
    reason = PatientStatusReason("  死亡による利用停止  ")
    assert reason.value == "死亡による利用停止"

    # 異常: 空文字
    with pytest.raises(DomainValidationError, match="空にできません"):
        PatientStatusReason("")

    # 異常: 長文（200文字超）
    with pytest.raises(DomainValidationError, match="200文字以内"):
        PatientStatusReason("あ" * 201)


def test_TC04_患者状態変更記録の不変条件() -> None:
    person_id, account_id, recorded_at = _actor_context()
    reason = PatientStatusReason("転居")

    # 異常: タイムゾーンなし
    with pytest.raises(DomainValidationError, match="タイムゾーンが必要"):
        PatientStatusChange(
            before=PatientStatus.ACTIVE,
            after=PatientStatus.INACTIVE,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=datetime(2026, 9, 21, 12, 0, 0),  # noqa: DTZ001
        )

    # 異常: MERGED なのに merged_into_id がない
    with pytest.raises(DomainValidationError, match="統合先患者IDが必要"):
        PatientStatusChange(
            before=PatientStatus.ACTIVE,
            after=PatientStatus.MERGED,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
            merged_into_id=None,
        )

    # 異常: MERGED 以外なのに merged_into_id がある
    with pytest.raises(DomainValidationError, match="統合先患者IDは指定できません"):
        PatientStatusChange(
            before=PatientStatus.ACTIVE,
            after=PatientStatus.INACTIVE,
            reason=reason,
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
            merged_into_id=PatientId.generate(),
        )


# ==============================================================================
# TC-06 〜 TC-08: 集約の不変条件
# ==============================================================================


def test_TC06_患者不変条件_マージ時は統合先IDが必須() -> None:
    patient = _create_patient()
    with pytest.raises(DomainValidationError, match="統合先患者IDが必要"):
        replace(patient, status=PatientStatus.MERGED, merged_into_id=None)


def test_TC07_患者不変条件_非マージ時は統合先ID禁止() -> None:
    patient = _create_patient()
    with pytest.raises(DomainValidationError, match="統合先患者IDは指定できません"):
        replace(
            patient,
            status=PatientStatus.ACTIVE,
            merged_into_id=PatientId.generate(),
        )


def test_TC08_患者不変条件_自身へのマージ禁止() -> None:
    patient = _create_patient()
    with pytest.raises(DomainValidationError, match="自身へ統合することはできません"):
        replace(
            patient,
            status=PatientStatus.MERGED,
            merged_into_id=patient.id,
        )


# ==============================================================================
# TC-09 〜 TC-14: 無効化・再有効化
# ==============================================================================


def test_TC09_有効患者の無効化() -> None:
    patient = _create_patient()
    person_id, account_id, recorded_at = _actor_context()
    reason = PatientStatusReason("転居")

    deactivated = patient.deactivate(
        reason=reason,
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    assert deactivated.status == PatientStatus.INACTIVE
    assert deactivated.is_active is False
    assert deactivated.is_merged is False
    assert len(deactivated.status_history) == 1
    assert deactivated.status_history[0].before == PatientStatus.ACTIVE
    assert deactivated.status_history[0].after == PatientStatus.INACTIVE
    assert deactivated.status_history[0].reason == reason


def test_TC10_無効化済み患者の無効化は冪等() -> None:
    patient = _create_patient()
    person_id, account_id, recorded_at = _actor_context()
    reason = PatientStatusReason("転居")

    deactivated = patient.deactivate(
        reason=reason,
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )
    again = deactivated.deactivate(
        reason=reason,
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    assert again is deactivated


def test_TC11_統合済み患者の無効化は拒否される() -> None:
    patient = _create_patient()
    target_id = PatientId.generate()
    person_id, account_id, recorded_at = _actor_context()
    merged = patient.merge_into(
        target_id,
        reason=PatientStatusReason("重複統合"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    with pytest.raises(PatientStateConflictError, match="統合済み"):
        merged.deactivate(
            reason=PatientStatusReason("死亡"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )


def test_TC12_無効患者の再有効化() -> None:
    patient = _create_patient()
    person_id, account_id, recorded_at = _actor_context()
    deactivated = patient.deactivate(
        reason=PatientStatusReason("誤無効化"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    reactivated = deactivated.reactivate(
        reason=PatientStatusReason("再来局のため再有効化"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    assert reactivated.status == PatientStatus.ACTIVE
    assert reactivated.is_active is True
    assert len(reactivated.status_history) == 2
    assert reactivated.status_history[1].before == PatientStatus.INACTIVE
    assert reactivated.status_history[1].after == PatientStatus.ACTIVE


def test_TC13_有効患者の再有効化は冪等() -> None:
    patient = _create_patient()
    person_id, account_id, recorded_at = _actor_context()
    again = patient.reactivate(
        reason=PatientStatusReason("有効化"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )
    assert again is patient


def test_TC14_統合済み患者の再有効化は拒否される() -> None:
    patient = _create_patient()
    target_id = PatientId.generate()
    person_id, account_id, recorded_at = _actor_context()
    merged = patient.merge_into(
        target_id,
        reason=PatientStatusReason("重複統合"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    with pytest.raises(PatientStateConflictError, match="統合済み"):
        merged.reactivate(
            reason=PatientStatusReason("復旧"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )


# ==============================================================================
# TC-15 〜 TC-18: マージ状態遷移・属性変更ガード
# ==============================================================================


def test_TC15_患者のマージ状態遷移() -> None:
    patient = _create_patient()
    target_id = PatientId.generate()
    person_id, account_id, recorded_at = _actor_context()
    reason = PatientStatusReason("旧姓と新姓の重複登録解消")

    merged = patient.merge_into(
        target_id,
        reason=reason,
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    assert merged.status == PatientStatus.MERGED
    assert merged.is_active is False
    assert merged.is_merged is True
    assert merged.merged_into_id == target_id
    assert len(merged.status_history) == 1
    assert merged.status_history[0].after == PatientStatus.MERGED
    assert merged.status_history[0].merged_into_id == target_id


def test_TC16_自身へのマージは拒否される() -> None:
    patient = _create_patient()
    person_id, account_id, recorded_at = _actor_context()

    with pytest.raises(
        PatientStateConflictError, match="自身へ統合することはできません"
    ):
        patient.merge_into(
            patient.id,
            reason=PatientStatusReason("自身統合"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )


def test_TC17_統合済み患者の再統合は拒否される() -> None:
    patient = _create_patient()
    target1_id = PatientId.generate()
    target2_id = PatientId.generate()
    person_id, account_id, recorded_at = _actor_context()

    merged = patient.merge_into(
        target1_id,
        reason=PatientStatusReason("初回統合"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    with pytest.raises(PatientStateConflictError, match="既に統合済み"):
        merged.merge_into(
            target2_id,
            reason=PatientStatusReason("再統合"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )


def test_TC18_統合済み患者の属性変更は拒否される() -> None:
    patient = _create_patient()
    target_id = PatientId.generate()
    person_id, account_id, recorded_at = _actor_context()

    merged = patient.merge_into(
        target_id,
        reason=PatientStatusReason("重複統合"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    new_names = PersonNames.create(
        last_name="佐藤",
        first_name="次郎",
        last_name_kana="サトウ",
        first_name_kana="ジロウ",
    )
    with pytest.raises(
        PatientStateConflictError, match="統合済みの患者の情報は変更できません"
    ):
        merged.change_names(new_names)

    with pytest.raises(
        PatientStateConflictError, match="統合済みの患者の情報は変更できません"
    ):
        merged.change_birth_date(PatientBirthDate(date(1995, 5, 5)))


# ==============================================================================
# TC-19 〜 TC-22: ドメインサービス（PatientMergeService）
# ==============================================================================


def test_TC19_マージサービス_正常系() -> None:
    corporate_id = CorporateId.generate()
    source = _create_patient(corporate_id=corporate_id, patient_number=1)
    target = _create_patient(corporate_id=corporate_id, patient_number=2)
    person_id, account_id, recorded_at = _actor_context()
    reason = PatientStatusReason("名寄せ統合")

    merged_source = PatientMergeService.merge(
        source,
        target,
        reason=reason,
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )

    assert merged_source.status == PatientStatus.MERGED
    assert merged_source.merged_into_id == target.id


def test_TC20_マージサービス_法人境界の検証() -> None:
    corp1 = CorporateId.generate()
    corp2 = CorporateId.generate()
    source = _create_patient(corporate_id=corp1)
    target = _create_patient(corporate_id=corp2)
    person_id, account_id, recorded_at = _actor_context()

    with pytest.raises(PatientStateConflictError, match="異なる法人の患者"):
        PatientMergeService.merge(
            source,
            target,
            reason=PatientStatusReason("異法人統合"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )


def test_TC21_マージサービス_ターゲット非アクティブの拒否() -> None:
    corporate_id = CorporateId.generate()
    source = _create_patient(corporate_id=corporate_id, patient_number=1)
    target = _create_patient(corporate_id=corporate_id, patient_number=2)
    person_id, account_id, recorded_at = _actor_context()

    # ターゲットがINACTIVEの場合
    deactivated_target = target.deactivate(
        reason=PatientStatusReason("転居"),
        person_id=person_id,
        account_id=account_id,
        recorded_at=recorded_at,
    )
    with pytest.raises(PatientStateConflictError, match="有効な患者を指定してください"):
        PatientMergeService.merge(
            source,
            deactivated_target,
            reason=PatientStatusReason("統合"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )


def test_TC22_マージサービス_同一患者の拒否() -> None:
    source = _create_patient()
    person_id, account_id, recorded_at = _actor_context()

    with pytest.raises(PatientStateConflictError, match="同一の患者"):
        PatientMergeService.merge(
            source,
            source,
            reason=PatientStatusReason("自身統合"),
            person_id=person_id,
            account_id=account_id,
            recorded_at=recorded_at,
        )
