"""NSIPS Uファイル（処方訂正）取込時の真正性管理テスト (TC-18, TC-19)。"""

from __future__ import annotations

import pytest

from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
)
from app.domain.medication_history import MedicationHistoryRecordId
from tests.application.integration.nsips.helpers import create_fixture


@pytest.mark.asyncio
async def test_ingest_u_file_with_finalized_history_records_correction() -> None:
    """TC-18: 確定済み薬歴が存在する処方箋に対しUファイルを受信した際、原本が保護され外部訂正証跡が記録される。"""
    fixture = await create_fixture()

    # 1. 初回受付（7日分処方）
    raw_initial = (
        "1,20260922,DOC-U01,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9001,ヤマダタロウ,山田太郎,1,19800101\n"
        "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_initial = await fixture.use_case.execute(
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            raw_nsips_text=raw_initial,
        )
    )
    assert res_initial.medication_history_id is not None
    history_id = MedicationHistoryRecordId.parse(res_initial.medication_history_id)

    # 2. 薬剤師が服薬指導を完了し薬歴を「確定（FINALIZED）」する
    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert history is not None
    finalized_history = history.finalize(finalized_by=fixture.pharmacist_id)
    await fixture.medication_history_repo.save(finalized_history)

    # 3. レセコン側で疑義照会等により日数変更され、同一処方箋番号でUファイル（5日分処方）が再送される
    raw_u_file = (
        "1,20260922,DOC-U01,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9001,ヤマダタロウ,山田太郎,1,19800101\n"
        "5,1,内服,1日3回毎食後,5,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_u_file = await fixture.use_case.execute(
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            raw_nsips_text=raw_u_file,
        )
    )

    # 4. 検証: 取込結果DTOで要確認が報告される
    assert res_u_file.has_pending_correction_review is True
    assert res_u_file.is_duplicate is False

    # 5. 検証: 確定薬歴の原本が1文字も破壊されていないこと（不可逆凍結の真正性保証）
    reloaded_history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert reloaded_history is not None
    assert reloaded_history.soap == finalized_history.soap
    assert reloaded_history.counseled_at == finalized_history.counseled_at
    assert reloaded_history.finalized_at == finalized_history.finalized_at
    assert reloaded_history.finalized_by == finalized_history.finalized_by
    assert reloaded_history.is_finalized is True

    # 6. 検証: 外部処方訂正の監査証跡が記録されていること
    assert len(reloaded_history.external_corrections) == 1
    assert reloaded_history.has_pending_correction_review is True


@pytest.mark.asyncio
async def test_ingest_u_file_with_draft_history() -> None:
    """TC-19: 下書き状態の薬歴が存在する処方箋に対しUファイルを受信した際の挙動検証。"""
    fixture = await create_fixture()

    # 1. 初回受付
    raw_initial = (
        "1,20260922,DOC-U02,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9002,サトウハナコ,佐藤花子,2,19850505\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_initial = await fixture.use_case.execute(
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            raw_nsips_text=raw_initial,
        )
    )
    history_id = MedicationHistoryRecordId.parse(
        res_initial.medication_history_id  # type: ignore[arg-type]
    )

    # 2. 薬歴は確定せず下書き（DRAFT）のままUファイル（7日分に変更）を受信
    raw_u_file = (
        "1,20260922,DOC-U02,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-9002,サトウハナコ,佐藤花子,2,19850505\n"
        "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
    )
    res_u_file = await fixture.use_case.execute(
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            operator_staff_id=str(fixture.pharmacist_id.value),
            raw_nsips_text=raw_u_file,
        )
    )

    history = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=history_id,
    )
    assert history is not None
    assert history.is_finalized is False
    assert res_u_file.has_pending_correction_review is False
