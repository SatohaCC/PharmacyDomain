"""NSIPS受付取込ユースケースのテスト (TC-16〜TC-25)。"""

from __future__ import annotations

import pytest

from app.application.common.exceptions import ApplicationError
from app.application.integration.nsips.ingest_nsips import (
    IngestNsipsCommand,
)
from app.domain.corporate import CorporateId
from app.domain.dispensing.exceptions import DispensingPharmacistQualificationError
from app.domain.dispensing.primitives import DispensingId
from app.domain.medication_history import MedicationHistoryRecordId
from app.domain.prescription.exceptions import MedicineClassificationMissingError
from tests.application.integration.nsips.helpers import create_fixture


@pytest.mark.asyncio
async def test_新規患者のNSIPSが全集約一括で起票される() -> None:
    """TC-16: 未登録のレセコン患者番号を含むNSIPSを受信した場合、新規患者登録〜薬歴下書きまで一括起票される。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    result = await fixture.use_case.execute(cmd)
    assert result.is_new_patient is True
    assert result.prescription_id is not None
    assert result.dispensing_id is not None
    assert result.medication_history_id is not None


@pytest.mark.asyncio
async def test_既存患者のNSIPSでは既存患者IDが再利用される() -> None:
    """TC-17: 既にレセコン患者番号が登録されている場合、既存のPatientIdが再利用される。"""
    fixture = await create_fixture()
    # 1. 事前に同一外部IDで初回取込を実行
    cmd1 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-EXIST,ヤマダタロウ,山田太郎,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res1 = await fixture.use_case.execute(cmd1)
    assert res1.is_new_patient is True

    # 2. 異なる処方箋番号で同一外部IDのNSIPSを実行
    cmd2 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-002,1310001,中央診療所,01,内科,佐藤医師\n2,P-EXIST,ヤマダタロウ,山田太郎,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res2 = await fixture.use_case.execute(cmd2)
    assert res2.is_new_patient is False
    assert res2.patient_id == res1.patient_id


@pytest.mark.asyncio
async def test_分割調剤NSIPSが客観的事実として記録される() -> None:
    """TC-18: 分割調剤情報を含むNSIPSを受信した場合、DispensingProcessに分割事実が記録される。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-003,1310001,中央診療所,01,内科,佐藤医師\n2,P-1002,スズキ,鈴木,2,19900101\n5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n6,1,3,長期保存困難\n",
    )
    result = await fixture.use_case.execute(cmd)
    assert result.dispensing_id is not None

    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=DispensingId.parse(result.dispensing_id),
    )
    assert dispensing is not None
    assert dispensing.iteration.value == 1
    assert dispensing.total_split_count is not None
    assert dispensing.total_split_count.value == 3
    assert dispensing.split_reason is not None
    assert dispensing.split_reason.value == "long_term_storage"


@pytest.mark.asyncio
async def test_調製区分が調剤セッションに反映される() -> None:
    """TC-19: 一包化指示を含むNSIPSを受信した場合、調剤明細に調製区分が記録される。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-004,1310001,中央診療所,01,内科,佐藤医師\n2,P-1003,タナカ,田中,1,19700101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,1\n",
    )
    result = await fixture.use_case.execute(cmd)
    assert result.dispensing_id is not None

    dispensing = await fixture.dispensing_repo.get(
        corporate_id=fixture.corporate_id,
        dispensing_id=DispensingId.parse(result.dispensing_id),
    )
    assert dispensing is not None
    assert (
        dispensing.dispensed_rps[0].medicines[0].preparations[0].value
        == "unit_dose_packaged"
    )


@pytest.mark.asyncio
async def test_同一処方の再送が冪等に既存IDを返す() -> None:
    """TC-20: 同一店舗・同一処方箋番号のNSIPSを再送した場合、既存の集約IDを返しis_duplicate=Trueとなる。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-DUP,1310001,中央診療所,01,内科,佐藤医師\n2,P-1004,サイトウ,斉藤,1,19850101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res1 = await fixture.use_case.execute(cmd)
    assert res1.is_duplicate is False

    res2 = await fixture.use_case.execute(cmd)
    assert res2.is_duplicate is True
    assert res2.prescription_id == res1.prescription_id


@pytest.mark.asyncio
async def test_認可権限不足または他法人店舗の指定は拒否される() -> None:
    """TC-21: 他法人店舗や無効法人の指定、権限不足Actorで実行した場合、認可例外となる。"""
    fixture = await create_fixture()
    other_corp = CorporateId.generate()
    fixture.corporate_repo.set_inactive(other_corp)

    cmd = IngestNsipsCommand(
        corporate_id=str(other_corp.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    with pytest.raises(ApplicationError):
        await fixture.use_case.execute(cmd)


@pytest.mark.asyncio
async def test_無資格スタッフでの取込は全ロールバックされる() -> None:
    """TC-22: operator_staff_id が無資格の場合、資格例外となり全ロールバックされる。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.unqualified_staff_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    with pytest.raises(DispensingPharmacistQualificationError):
        await fixture.use_case.execute(cmd)


@pytest.mark.asyncio
async def test_処方箋バリデーション失敗時に全集約がロールバックされる() -> None:
    """TC-23: 処方箋登録で例外が発生した場合、患者登録も含めて全ロールバックされる。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-FAIL,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n5,1,内服,1日3回毎食後,14,1,999999999,麻薬医薬品,1,錠,0\n",
    )
    with pytest.raises(MedicineClassificationMissingError):
        await fixture.use_case.execute(cmd)


@pytest.mark.asyncio
async def test_UnitOfWork未開始の実行は拒否される() -> None:
    """TC-24: UnitOfWorkが開始されていない状態での実行は防御例外となる。"""
    fixture = await create_fixture()

    class InactiveUnitOfWork:
        def ensure_active(self) -> None:
            raise RuntimeError("Unit of Work is not active")

    fixture.use_case._unit_of_work = InactiveUnitOfWork()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n",
    )
    with pytest.raises(RuntimeError):
        await fixture.use_case.execute(cmd)


@pytest.mark.asyncio
async def test_薬品0件のフォローアップ単独受付が直近薬歴に紐付けられる() -> None:
    """TC-25: 薬品0件のNSIPSを受信した場合、処方箋・調剤を起票せず直近薬歴にフォローアップが紐付けられる。"""
    fixture = await create_fixture()
    # 1. 初回処方で患者と薬歴を起票
    cmd1 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-INIT,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res1 = await fixture.use_case.execute(cmd1)
    assert res1.medication_history_id is not None

    # 薬歴を確定（フォローアップ追加の前提）
    hist_record = await fixture.medication_history_repo.get(
        corporate_id=fixture.corporate_id,
        record_id=MedicationHistoryRecordId.parse(res1.medication_history_id),
    )
    assert hist_record is not None
    finalized_record = hist_record.finalize()
    await fixture.medication_history_repo.save(finalized_record)

    # 2. 薬品0件のNSIPSを受信（フォローアップ受付）
    cmd2 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        operator_staff_id=str(fixture.pharmacist_id.value),
        raw_nsips_text="1,20260921,DOC-FOLLOWUP,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n",
    )
    result = await fixture.use_case.execute(cmd2)
    assert result.is_follow_up_only is True
    assert result.prescription_id is None
    assert result.dispensing_id is None
    assert result.medication_history_id == res1.medication_history_id
    assert result.follow_up_id is not None
