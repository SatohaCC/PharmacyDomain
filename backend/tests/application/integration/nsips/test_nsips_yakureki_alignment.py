"""Yakureki仕様に準拠したNSIPS取込（ファイル名・台帳・A/U/D/B操作）のテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.application.integration.boundary_models import (
    NsipsBundle,
    NsipsDrugSupplementInfo,
    NsipsFileStatus,
    NsipsInsuranceInfo,
    NsipsMedicineInfo,
    NsipsNarcoticInfo,
    NsipsOperation,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRemarkInfo,
    NsipsRpInfo,
    NsipsRpUsageSupplementInfo,
)
from app.application.integration.commands.ingest_nsips import IngestNsipsCommand
from app.application.integration.errors import NsipsReceptionNotFoundError
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import ReceptionSourceStatus
from tests.application.integration.nsips.helpers import create_fixture


def _sample_bundle(
    *,
    doc_number: str = "DOC-YAKUREKI-001",
    days_supply: int = 14,
    with_narcotics: bool = False,
) -> NsipsBundle:
    """Yakureki準拠のテスト用Bundleを生成する。"""
    narcotic_info = (
        NsipsNarcoticInfo(
            license_number="NARCO-12345",
            patient_address="東京都千代田区1-1-1",
            patient_phone="03-1111-2222",
        )
        if with_narcotics
        else None
    )
    return NsipsBundle(
        header_version="yakureki-test",
        patient=NsipsPatientInfo(
            external_patient_id="P-YAKUREKI-001",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1990, 1, 1),
            gender="1",
            postal_code="100-0001",
            address="東京都千代田区1-1-1",
            phone_number="03-1111-2222",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number=doc_number,
            issued_date=date(2026, 6, 22),
            institution_code="1310001",
            institution_name="千代田クリニック",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤一郎",
            expiration_date=date(2026, 6, 26),
            narcotic_info=narcotic_info,
            remaining_medication_check_code="1",
            refill_total_uses=3,
            remarks=(
                NsipsRemarkInfo(
                    sequence_number=1,
                    remark_type_code="01",
                    text="一包化希望",
                ),
            ),
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="1日3回毎食後",
                    dispensing_quantity=days_supply,
                    dosage_form_code="1",
                    dosage_form_name="内服錠",
                    usage_code="101",
                    daily_frequency=3,
                    usage_supplements=(
                        NsipsRpUsageSupplementInfo(
                            category_code="01",
                            text="粉砕不可",
                        ),
                    ),
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="610406001",
                            medicine_name="ロキソニン錠60mg",
                            dosage=Decimal("1"),
                            unit="錠",
                            days_supply=days_supply,
                            yj_code="1149019F1030",
                            info_category="drug",
                            supplements=(
                                NsipsDrugSupplementInfo(
                                    category_code="01",
                                    text="後発医薬品変更不可",
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        dispensed_date=date(2026, 6, 22),
        insurance=NsipsInsuranceInfo(
            insurer_number="123456",
            insured_symbol="12",
            insured_number="345678",
        ),
    )


@pytest.mark.asyncio
async def test_NSIPS登録ファイル_Aプレフィックス_台帳にappliedが記録され受付IDが自動採番される() -> (
    None
):
    """A_<file_id>.xml を指定すると受付ID未指定でも採番され、台帳に applied が記録される。"""
    # Arrange
    fixture = await create_fixture()
    bundle = _sample_bundle(with_narcotics=True)
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="A_20260622-0001.xml",
        structured_bundle=bundle,
    )

    # Act
    result = await fixture.use_case.execute(command)

    # Assert
    assert result.file_id == "20260622-0001"
    assert result.operation == "create"
    assert result.status == "applied"
    assert result.was_already_applied is False
    assert result.reception_id is not None

    reception_id = ReceptionId.parse(result.reception_id)
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.source_status == ReceptionSourceStatus.CURRENT

    ledger = await fixture.nsips_file_repo.get_by_identity(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        file_id="20260622-0001",
        operation=NsipsOperation.CREATE,
    )
    assert ledger is not None
    assert ledger.status is NsipsFileStatus.APPLIED
    assert ledger.target_reception_id == reception_id


@pytest.mark.asyncio
async def test_NSIPS登録ファイル再送_同一内容_台帳からwas_already_appliedが返る() -> (
    None
):
    """同一内容の A_<file_id>.xml を再送すると台帳で検知され was_already_applied=True となる。"""
    # Arrange
    fixture = await create_fixture()
    bundle = _sample_bundle()
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="A_20260622-0002.xml",
        structured_bundle=bundle,
    )
    initial = await fixture.use_case.execute(command)
    assert initial.was_already_applied is False

    # Act: 同一ファイルの再送
    duplicate = await fixture.use_case.execute(command)

    # Assert
    assert duplicate.was_already_applied is True
    assert duplicate.status == "applied"
    assert duplicate.reception_id == initial.reception_id


@pytest.mark.asyncio
async def test_NSIPS訂正ファイル_Uプレフィックス_同一file_idの受付に訂正が適用される() -> (
    None
):
    """登録後に U_<file_id>.xml を送信すると、受付ID指定なしで同一受付に訂正が反映される。"""
    # Arrange: 初回登録
    fixture = await create_fixture()
    initial_bundle = _sample_bundle(days_supply=14)
    create_cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="A_20260622-0003.xml",
        structured_bundle=initial_bundle,
    )
    created = await fixture.use_case.execute(create_cmd)
    rec_id = ReceptionId.parse(created.reception_id)

    # Act: 日数を28日に変更した訂正ファイルを送信
    updated_bundle = _sample_bundle(days_supply=28)
    update_cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="U_20260622-0003.xml",
        structured_bundle=updated_bundle,
    )
    updated = await fixture.use_case.execute(update_cmd)

    # Assert
    assert updated.file_id == "20260622-0003"
    assert updated.operation == "update"
    assert updated.status == "applied"
    assert updated.reception_id == created.reception_id

    # 台帳にUPDATEエントリがAPPLIEDで記録されていること
    update_ledger = await fixture.nsips_file_repo.get_by_identity(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        file_id="20260622-0003",
        operation=NsipsOperation.UPDATE,
    )
    assert update_ledger is not None
    assert update_ledger.status is NsipsFileStatus.APPLIED
    assert update_ledger.target_reception_id == rec_id


@pytest.mark.asyncio
async def test_NSIPS取消ファイル_Dプレフィックス_処方本文なしで受付がwithdrawn取消される() -> (
    None
):
    """D_<file_id>.xml を本文なしで送信すると、対象受付が WITHDRAWN に取り消される。"""
    # Arrange: 初回登録
    fixture = await create_fixture()
    bundle = _sample_bundle()
    create_cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="A_20260622-0004.xml",
        structured_bundle=bundle,
    )
    created = await fixture.use_case.execute(create_cmd)
    rec_id = ReceptionId.parse(created.reception_id)

    # Act: 処方本文なしの取消ファイルを送信
    delete_cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="D_20260622-0004.xml",
    )
    deleted = await fixture.use_case.execute(delete_cmd)

    # Assert
    assert deleted.file_id == "20260622-0004"
    assert deleted.operation == "delete"
    assert deleted.status == "applied"
    assert deleted.reception_id == created.reception_id

    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=rec_id,
    )
    assert reception is not None
    assert reception.source_status == ReceptionSourceStatus.WITHDRAWN

    del_ledger = await fixture.nsips_file_repo.get_by_identity(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        file_id="20260622-0004",
        operation=NsipsOperation.DELETE,
    )
    assert del_ledger is not None
    assert del_ledger.status is NsipsFileStatus.APPLIED


@pytest.mark.asyncio
async def test_NSIPS一括ファイル_Bプレフィックス_初回は登録で2回目は訂正として扱われる() -> (
    None
):
    """B_<file_id>.xml は初回受信で CREATE、同一file_idの2通目受信で UPDATE として扱われる。"""
    fixture = await create_fixture()
    bundle_1 = _sample_bundle(days_supply=7)
    cmd_1 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="B_20260622-0005.xml",
        structured_bundle=bundle_1,
    )
    res_1 = await fixture.use_case.execute(cmd_1)
    assert res_1.operation == "create"
    assert res_1.status == "applied"

    # 2回目（内容変更）
    bundle_2 = _sample_bundle(days_supply=14)
    cmd_2 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="B_20260622-0005.xml",
        structured_bundle=bundle_2,
    )
    res_2 = await fixture.use_case.execute(cmd_2)
    assert res_2.operation == "update"
    assert res_2.status == "applied"
    assert res_2.reception_id == res_1.reception_id


@pytest.mark.asyncio
async def test_NSIPS訂正ファイル_未登録のfile_id_台帳にfailedが記録されエラーとなる() -> (
    None
):
    """未登録の file_id に対する U ファイルはエラーとなり、台帳に FAILED と理由が記録される。"""
    fixture = await create_fixture()
    bundle = _sample_bundle()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        file_name="U_UNKNOWN-999.xml",
        structured_bundle=bundle,
    )

    with pytest.raises(NsipsReceptionNotFoundError):
        await fixture.use_case.execute(cmd)

    failed_ledger = await fixture.nsips_file_repo.get_by_identity(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        file_id="UNKNOWN-999",
        operation=NsipsOperation.UPDATE,
    )
    assert failed_ledger is not None
    assert failed_ledger.status is NsipsFileStatus.FAILED
    assert "見つかりません" in failed_ledger.error_text
