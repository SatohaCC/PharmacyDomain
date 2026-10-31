"""NSIPS受付取込ユースケースのテスト (TC-16〜TC-25)。"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.application.common.exceptions import ApplicationError
from app.application.integration.boundary_models import (
    NsipsBundle,
    NsipsMedicineInfo,
    NsipsPatientInfo,
    NsipsPrescriptionInfo,
    NsipsRpInfo,
)
from app.application.integration.commands.ingest_nsips import IngestNsipsCommand
from app.application.integration.commands.services.parser import NsipsParser
from app.application.integration.errors import NsipsParseError
from app.domain.corporate.identifiers import CorporateId
from app.domain.medication_history.primitives import ExternalCorrectionKind
from app.domain.patient.entities import Patient, PatientExternalIdentifier
from app.domain.patient.identifiers import PatientExternalIdentifierId, PatientId
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientHeadingText,
    PatientHeadingTimestamp,
)
from app.domain.patient.value_objects import (
    PatientHeadingContent,
    PatientHeadingRevision,
)
from app.domain.reception.entities import Reception
from app.domain.reception.identifiers import ReceptionId
from app.domain.reception.primitives import ReceptionFingerprint
from app.domain.shared.actor import AccountPersonId, UserAccountId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.value_objects import AffiliationPeriod, StoreAffiliation
from app.domain.store.identifiers import StoreId
from tests.application.integration.nsips.helpers import (
    create_fixture,
    execute_structured_test_command,
)
from tests.factories.medication_history_factory import (
    create_record,
    create_soap,
    finalize_record_with_review,
)
from tests.factories.store_factory import create_store


def _minimal_structured_bundle(document_number: str) -> NsipsBundle:
    """受付ID境界テスト用の妥当な、Rpを含まないBundleを返す。"""
    return NsipsBundle(
        header_version="structured-test",
        patient=NsipsPatientInfo(
            external_patient_id="P-TC50",
            kanji_name="山田太郎",
            kana_name="ヤマダタロウ",
            birth_date=date(1980, 1, 1),
            gender="1",
        ),
        prescription=NsipsPrescriptionInfo(
            document_number=document_number,
            issued_date=date(2026, 9, 23),
            institution_code="1310001",
            institution_name="中央診療所",
            department_code="01",
            department_name="内科",
            doctor_name="佐藤医師",
            rps=(),
        ),
    )


class _UnsupportedNsipsVersionParser(NsipsParser):
    """対応版一覧に無い識別子を返すテスト用Parser。"""

    def __init__(self, bundle: NsipsBundle) -> None:
        self._bundle = bundle

    def parse(self, raw_text: str) -> NsipsBundle:
        """テストで与えた未登録版のBundleを返す。"""
        return self._bundle


@pytest.mark.asyncio
async def test_新規患者のNSIPSが全集約一括で起票される() -> None:
    """未登録患者のNSIPS取込では受付まで保存し、薬歴・処方・調剤は作らない。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    result = await execute_structured_test_command(fixture, cmd)
    assert result.is_new_patient is True
    assert result.prescription_id is None
    assert result.dispensing_id is None
    assert result.medication_history_id is None
    assert fixture.medication_history_repo.items == {}
    assert fixture.prescription_repo.items == {}
    assert fixture.dispensing_repo.items == {}
    reception = next(iter(fixture.reception_repo.items.values()))
    assert reception.medication_history_id is None
    assert reception.dispensing_id is None
    assert reception.prescription_id is None


@pytest.mark.asyncio
async def test_NSIPS初回取込_薬品一件_保存処方と調剤の識別情報が一致する() -> None:
    """初回取込は原本を保存し処方・調剤集約は自動生成しない。"""
    # Arrange
    fixture = await create_fixture()
    bundle = _minimal_structured_bundle("DOC-MEDICINE-INITIAL")
    bundle = replace(
        bundle,
        prescription=replace(
            bundle.prescription,
            issued_date=date(2026, 9, 21),
            rps=(
                NsipsRpInfo(
                    rp_number=1,
                    group_name="内服",
                    instructions="1日3回毎食後",
                    dispensing_quantity=14,
                    medicines=(
                        NsipsMedicineInfo(
                            medicine_code="610406001",
                            medicine_name="アムロジピン",
                            dosage=Decimal("1"),
                            unit="錠",
                        ),
                    ),
                ),
            ),
        ),
        dispensed_date=date(2026, 9, 21),
    )
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        structured_bundle=bundle,
    )

    # Act
    result = await execute_structured_test_command(fixture, command)

    # Assert
    assert result.is_new_patient
    assert not result.is_duplicate
    assert result.prescription_id is None
    assert result.dispensing_id is None
    assert len(fixture.patient_repo.items) == 1
    assert len(fixture.reception_repo.items) == 1
    assert len(fixture.prescription_repo.items) == 0
    assert len(fixture.dispensing_repo.items) == 0
    assert result.medication_history_id is None
    assert fixture.medication_history_repo.items == {}


@pytest.mark.asyncio
async def test_tc45_未確認版のraw入力は書込み前に拒否される() -> None:
    """対応版と列定義が未確認のraw形式は解析成功しても受け付けない。"""
    fixture = await create_fixture()
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text=(
            "1,20260921,DOC-UNVERIFIED,1310001,中央診療所,01,内科,佐藤医師\n"
            "2,P-UNVERIFIED,ヤマダタロウ,山田太郎,1,19800101\n"
            "4,20260921,REC-001,調剤花子\n"
            "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
        ),
    )

    with pytest.raises(NsipsParseError):
        await fixture.use_case.execute(command)

    assert fixture.patient_repo.items == {}
    assert fixture.patient_external_id_repo.items == {}
    assert fixture.patient_coverage_repo.items == {}
    assert fixture.coverage_selection_repo.items == {}
    assert fixture.prescription_repo.items == {}
    assert fixture.dispensing_repo.items == {}
    assert fixture.medication_history_repo.items == {}


@pytest.mark.asyncio
async def test_tc45_未登録のraw版識別子も書込み前に拒否される() -> None:
    """Parserが未知の版識別子を返しても、許可リストに無ければ拒否する。"""
    fixture = await create_fixture()
    raw_text = (
        "1,20260921,DOC-UNREGISTERED,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-UNREGISTERED,ヤマダタロウ,山田太郎,1,19800101\n"
        "4,20260921,REC-001,調剤花子\n"
        "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
    )
    parsed = NsipsParser().parse(raw_text)
    fixture.use_case._parser = _UnsupportedNsipsVersionParser(
        replace(parsed, header_version="unregistered-v2")
    )
    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text=raw_text,
    )

    with pytest.raises(NsipsParseError):
        await fixture.use_case.execute(command)

    assert fixture.patient_repo.items == {}
    assert fixture.patient_external_id_repo.items == {}
    assert fixture.patient_coverage_repo.items == {}
    assert fixture.coverage_selection_repo.items == {}
    assert fixture.prescription_repo.items == {}
    assert fixture.dispensing_repo.items == {}
    assert fixture.medication_history_repo.items == {}


@pytest.mark.asyncio
async def test_既存患者のNSIPSでは既存患者IDが再利用される() -> None:
    """TC-17とTC-43-48: 再取込で患者IDを保ち、頭書き履歴や既存属性を自動上書きしない。"""
    fixture = await create_fixture()
    # 1. 事前に同一外部IDで初回取込を実行
    cmd1 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-EXIST,ヤマダタロウ,山田太郎,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res1 = await execute_structured_test_command(fixture, cmd1)
    assert res1.is_new_patient is True
    assert res1.patient_id is not None
    patient_id = PatientId.parse(res1.patient_id)
    patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id, patient_id=patient_id
    )
    assert patient is not None
    heading = PatientHeadingRevision(
        content=PatientHeadingContent(
            summary=PatientHeadingText("再取込前の申し送り"),
            notes=PatientHeadingText("NSIPSでは更新しない記録"),
        ),
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
        recorded_at=PatientHeadingTimestamp(datetime(2026, 9, 23, tzinfo=UTC)),
    )
    await fixture.patient_repo.save(replace(patient, heading_history=(heading,)))

    # 2. 異なる処方箋番号で同一外部IDのNSIPSを実行
    cmd2 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-002,1310001,中央診療所,01,内科,佐藤医師\n2,P-EXIST,ヤマダジロウ,山田次郎,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res2 = await execute_structured_test_command(fixture, cmd2)
    assert res2.is_new_patient is False
    assert res2.patient_id == res1.patient_id
    updated_patient = await fixture.patient_repo.get(
        corporate_id=fixture.corporate_id, patient_id=patient_id
    )
    assert updated_patient is not None
    # 既存の患者属性（山田太郎）を自動上書きしない
    assert updated_patient.names.kanji.last_name.value == "山田"
    assert updated_patient.names.kanji.first_name.value == "太郎"
    assert updated_patient.heading_history == (heading,)


@pytest.mark.asyncio
async def test_分割調剤NSIPSが客観的事実として記録される() -> None:
    """TC-18: 分割調剤情報を含むNSIPSを受信した場合、受付集約の原本に客観的事実が記録される。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-003,1310001,中央診療所,01,内科,佐藤医師\n2,P-1002,スズキ,鈴木,2,19900101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n6,1,3,長期保存困難\n",
    )
    result = await execute_structured_test_command(fixture, cmd)
    assert result.dispensing_id is None
    assert result.prescription_id is None

    reception = next(iter(fixture.reception_repo.items.values()))
    assert reception.source_data is not None
    assert "長期保存困難" in reception.source_data.bundle_json.value


@pytest.mark.asyncio
async def test_調製区分が調剤セッションに反映される() -> None:
    """TC-19: 一包化指示を含むNSIPSを受信した場合、受付集約の原本に調製区分が記録される。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-004,1310001,中央診療所,01,内科,佐藤医師\n2,P-1003,タナカ,田中,1,19700101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,1\n",
    )
    result = await execute_structured_test_command(fixture, cmd)
    assert result.dispensing_id is None

    reception = next(iter(fixture.reception_repo.items.values()))
    assert reception.source_data is not None
    assert "610406001" in reception.source_data.bundle_json.value


@pytest.mark.asyncio
async def test_tc32_同一Bundle再送で受付集約を重複作成しない() -> None:
    """同じ処方箋番号の同一入力は既存IDを返し、全Fake Repositoryを増やさない。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-DUP,1310001,中央診療所,01,内科,佐藤医師\n2,P-1004,サイトウ,斉藤,1,19850101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res1 = await execute_structured_test_command(fixture, cmd)
    assert res1.is_duplicate is False

    res2 = await execute_structured_test_command(fixture, cmd)
    assert res2.is_duplicate is True
    assert res2.reception_id == res1.reception_id
    assert res2.prescription_id is None
    assert res2.dispensing_id is None
    assert res1.medication_history_id is None
    assert res2.medication_history_id is None
    assert len(fixture.patient_repo.items) == 1
    assert len(fixture.patient_external_id_repo.items) == 1
    assert len(fixture.prescription_repo.items) == 0
    assert len(fixture.dispensing_repo.items) == 0
    assert len(fixture.reception_repo.items) == 1
    assert fixture.medication_history_repo.items == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_kind",
    ("missing", "malformed", "uuid4"),
    ids=("受付IDなし", "UUID形式不正", "UUIDv4"),
)
async def test_tc50_取込CommandはUUIDv7以外の受付IDで書き込まない(
    invalid_kind: str,
) -> None:
    """HTTP境界を通さないCommandでも受付IDの必須性とUUIDv7を守る。"""
    fixture = await create_fixture()
    reception_id: str | None = None
    if invalid_kind == "malformed":
        reception_id = "not-a-uuid"
    elif invalid_kind == "uuid4":
        reception_id = str(uuid.uuid4())

    command = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        reception_id=reception_id,
        structured_bundle=_minimal_structured_bundle(f"DOC-TC50-{invalid_kind}"),
    )

    with pytest.raises(ApplicationError):
        await fixture.use_case.execute(command)

    assert fixture.patient_repo.items == {}
    assert fixture.patient_external_id_repo.items == {}
    assert fixture.prescription_repo.items == {}
    assert fixture.dispensing_repo.items == {}
    assert fixture.medication_history_repo.items == {}
    assert fixture.reception_repo.items == {}


@pytest.mark.asyncio
async def test_tc54_同じ処方箋番号でも別受付IDなら別患者へ紐付く() -> None:
    """紙処方箋番号の衝突で異なる受付を同一患者へ結び付けない。"""
    fixture = await create_fixture()
    first_reception_id = ReceptionId.generate()
    second_reception_id = ReceptionId.generate()
    first = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        reception_id=str(first_reception_id.value),
        raw_nsips_text=(
            "1,20260922,DOC-COLLISION,1310001,中央診療所,01,内科,佐藤医師\n"
            "2,P-COLLISION-A,ヤマダタロウ,山田太郎,1,19800101\n"
            "4,20260922,REC-001,調剤花子\n"
            "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
        ),
    )
    second = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        reception_id=str(second_reception_id.value),
        raw_nsips_text=(
            "1,20260922,DOC-COLLISION,1310001,中央診療所,01,内科,佐藤医師\n"
            "2,P-COLLISION-B,サトウハナコ,佐藤花子,2,19850505\n"
            "4,20260922,REC-002,調剤花子\n"
            "5,1,内服,1日2回食後,5,1,610406001,アムロジピン,1,錠,0\n"
        ),
    )

    first_result = await execute_structured_test_command(fixture, first)
    second_result = await execute_structured_test_command(fixture, second)

    assert first_result.patient_id != second_result.patient_id
    assert second_result.is_duplicate is False
    assert len(fixture.reception_repo.items) == 2


@pytest.mark.asyncio
async def test_tc55_別店舗で同じ受付IDを独立した受付として処理する() -> None:
    """店舗ごとに発行された同じ受付IDを別々の受付として扱う。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    original_reception = Reception(
        id=reception_id,
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=PatientId.generate(),
        prescription_id=None,
        latest_fingerprint=ReceptionFingerprint("a" * 64),
        field_fingerprints=(),
    )
    await fixture.reception_repo.save(original_reception)

    other_store_id = StoreId.generate()
    other_store = replace(
        create_store(corporate_id=fixture.corporate_id, name="TC55別店舗"),
        id=other_store_id,
    )
    await fixture.store_repo.save(other_store)
    pharmacist = await fixture.staff_repo.get(
        corporate_id=fixture.corporate_id,
        staff_id=fixture.pharmacist_id,
    )
    assert pharmacist is not None
    await fixture.staff_repo.save(
        replace(
            pharmacist,
            affiliations=(
                *pharmacist.affiliations,
                StoreAffiliation(
                    store_id=other_store_id,
                    is_primary=False,
                    period=AffiliationPeriod(start_date=date(2026, 1, 1)),
                ),
            ),
        )
    )

    second_result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(other_store_id.value),
            reception_id=str(reception_id.value),
            raw_nsips_text=(
                "1,20260922,DOC-TC55,1310001,中央診療所,01,内科,佐藤医師\n"
                "2,P-TC55-B,サトウハナコ,佐藤花子,2,19850505\n"
                "4,20260922,REC-002,調剤花子\n"
                "5,1,内服,1日2回食後,5,1,610406001,アムロジピン,1,錠,0\n"
            ),
        ),
    )
    assert second_result.is_duplicate is False
    assert PatientId.parse(second_result.patient_id) != original_reception.patient_id

    other_store_reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=other_store_id,
        reception_id=reception_id,
    )
    assert other_store_reception is not None
    assert other_store_reception.patient_id == PatientId.parse(second_result.patient_id)
    assert (
        other_store_reception.latest_fingerprint
        != original_reception.latest_fingerprint
    )

    unchanged_reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert unchanged_reception is not None
    assert unchanged_reception.patient_id == original_reception.patient_id
    assert unchanged_reception.prescription_id == original_reception.prescription_id
    assert (
        unchanged_reception.latest_fingerprint == original_reception.latest_fingerprint
    )
    assert (
        unchanged_reception.correction_history == original_reception.correction_history
    )
    assert len(fixture.reception_repo.items) == 2
    assert len(fixture.patient_repo.items) == 1
    assert len(fixture.prescription_repo.items) == 0


@pytest.mark.asyncio
async def test_tc64_店舗未指定の旧外部IDを店舗別取込で採用しない() -> None:
    """未スコープの旧リンクから新店舗へ誤って患者を結び付けない。"""
    fixture = await create_fixture()
    legacy_patient = Patient(
        id=PatientId.generate(),
        corporate_id=fixture.corporate_id,
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("旧"), first_name=PersonNamePart("患者")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("キュウ"),
                first_name=PersonNameKanaPart("カンジャ"),
            ),
        ),
        patient_number=await fixture.patient_repo.allocate_patient_number(
            fixture.corporate_id
        ),
        birth_date=None,
        gender=None,
        postal_code=None,
        address=None,
        phone_number=None,
    )
    await fixture.patient_repo.save(legacy_patient)
    await fixture.patient_external_id_repo.save(
        PatientExternalIdentifier(
            id=PatientExternalIdentifierId.generate(),
            corporate_id=fixture.corporate_id,
            patient_id=legacy_patient.id,
            system_name=ExternalSystemName("recept"),
            external_patient_id=ExternalPatientId("P-TC64-LEGACY"),
            store_id=None,
        )
    )

    result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(ReceptionId.generate().value),
            raw_nsips_text=(
                "1,20260922,DOC-TC64,1310001,中央診療所,01,内科,佐藤医師\n"
                "2,P-TC64-LEGACY,キュウカンジャ,旧患者,1,19800101\n"
                "4,20260922,REC-001,調剤花子\n"
                "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
            ),
        ),
    )

    assert result.patient_id != str(legacy_patient.id.value)
    old_links = await fixture.patient_external_id_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=legacy_patient.id,
    )
    assert len(old_links) == 1
    assert old_links[0].store_id is None
    new_links = await fixture.patient_external_id_repo.list_by_patient(
        corporate_id=fixture.corporate_id,
        patient_id=PatientId.parse(result.patient_id),
    )
    assert new_links
    assert new_links[0].store_id == fixture.store_id


@pytest.mark.asyncio
async def test_tc65_氏名と生年月日が一致しても患者を自動統合しない() -> None:
    """別のレセコン患者IDは氏名が同じでも別Patientとして扱う。"""
    fixture = await create_fixture()
    first = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(ReceptionId.generate().value),
            raw_nsips_text=(
                "1,20260922,DOC-TC65-A,1310001,中央診療所,01,内科,佐藤医師\n"
                "2,P-TC65-A,ヤマダタロウ,山田太郎,1,19800101\n"
                "4,20260922,REC-001,調剤花子\n"
                "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
            ),
        ),
    )
    second = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(ReceptionId.generate().value),
            raw_nsips_text=(
                "1,20260922,DOC-TC65-B,1310001,中央診療所,01,内科,佐藤医師\n"
                "2,P-TC65-B,ヤマダタロウ,山田太郎,1,19800101\n"
                "4,20260922,REC-002,調剤花子\n"
                "5,1,内服,1日3回毎食後,7,1,610406001,アムロジピン,1,錠,0\n"
            ),
        ),
    )

    assert first.patient_id != second.patient_id


@pytest.mark.asyncio
async def test_認可権限不足または他法人店舗の指定は拒否される() -> None:
    """TC-41: 他法人店舗や無効法人の指定では認可例外となる。"""
    fixture = await create_fixture()
    other_corp = CorporateId.generate()
    fixture.corporate_repo.set_inactive(other_corp)

    cmd = IngestNsipsCommand(
        corporate_id=str(other_corp.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    with pytest.raises(ApplicationError):
        await execute_structured_test_command(fixture, cmd)


@pytest.mark.asyncio
async def test_tc019_tc134_無資格スタッフでも原本受信は成功する() -> None:
    """TC-019/TC-134: 原本受信は非薬剤師スタッフでも成功し、調剤開始などの明示業務に資格が要求される。"""
    fixture = await create_fixture()
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    result = await execute_structured_test_command(fixture, cmd, use_unqualified=True)
    assert result.reception_id is not None
    assert result.prescription_id is None
    assert result.dispensing_id is None
    assert fixture.patient_repo.items
    assert fixture.patient_external_id_repo.items
    assert fixture.reception_repo.items
    assert fixture.prescription_repo.items == {}
    assert fixture.dispensing_repo.items == {}


@pytest.mark.asyncio
async def test_Fakeでは受付保存失敗前の患者保存が残る() -> None:
    """NullUnitOfWorkとFakeでは先行保存が残り、原子性の証明にならない。"""
    fixture = await create_fixture()

    async def failing_save(reception: Any) -> None:
        raise RuntimeError("Simulated reception save failure")

    fixture.reception_repo.save = failing_save  # type: ignore[method-assign]
    cmd = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-FAIL,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,999999999,麻薬医薬品,1,錠,0\n",
    )
    with pytest.raises(RuntimeError, match="Simulated reception save failure"):
        await execute_structured_test_command(fixture, cmd)

    assert fixture.patient_repo.items
    assert fixture.patient_external_id_repo.items


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
        raw_nsips_text="1,20260921,DOC-001,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダ,山田,1,19800101\n",
    )
    with pytest.raises(RuntimeError):
        await execute_structured_test_command(fixture, cmd)


@pytest.mark.asyncio
async def test_tc07_薬歴未作成のフォローアップ単独受付を受付側へ保留する() -> None:
    """薬歴未作成時のフォローアップは薬歴を作らず受付側に保留する。"""
    fixture = await create_fixture()
    # 1. 初回処方で患者と薬歴を起票
    cmd1 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-INIT,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n4,20260921,REC-001,調剤花子\n5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n",
    )
    res1 = await execute_structured_test_command(fixture, cmd1)
    assert res1.medication_history_id is None
    assert fixture.medication_history_repo.items == {}

    # 2. 薬品0件のNSIPSを受信（フォローアップ受付）
    cmd2 = IngestNsipsCommand(
        corporate_id=str(fixture.corporate_id.value),
        store_id=str(fixture.store_id.value),
        raw_nsips_text="1,20260921,DOC-FOLLOWUP,1310001,中央診療所,01,内科,佐藤医師\n2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n",
    )
    result = await execute_structured_test_command(fixture, cmd2)
    assert result.is_follow_up_only is True
    assert result.prescription_id is None
    assert result.dispensing_id is None
    assert result.medication_history_id is None
    assert result.follow_up_id is None
    assert fixture.medication_history_repo.items == {}
    follow_up_reception = max(
        fixture.reception_repo.items.values(),
        key=lambda reception: reception.id.value,
    )
    assert follow_up_reception.medication_history_id is None
    source_data = getattr(follow_up_reception, "source_data", None)
    assert source_data is not None
    assert source_data.is_follow_up is True
    assert "DOC-FOLLOWUP" in source_data.bundle_json.value


@pytest.mark.asyncio
async def test_tc09_既存受付に明示関連付けした薬歴も自動更新しない() -> None:
    """U-fileはリンク済み薬歴を更新せず受付の受信履歴にだけ保管する。"""
    fixture = await create_fixture()
    reception_id = ReceptionId.generate()
    initial = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(reception_id.value),
            raw_nsips_text=(
                "1,20260921,DOC-FOLLOWUP-LINKED,1310001,中央診療所,01,内科,佐藤医師\n"
                "2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n"
                "4,20260921,REC-LINKED,調剤花子\n"
                "5,1,内服,1日3回毎食後,14,1,610406001,アムロジピン,1,錠,0\n"
            ),
        ),
    )
    assert initial.medication_history_id is None
    assert initial.dispensing_id is None
    authored_record = finalize_record_with_review(
        create_record(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=PatientId.parse(initial.patient_id),
            dispensing_id=None,
            prescription_id=None,
            counselor_id=fixture.pharmacist_id,
            counseled_at=fixture.clock.now(),
            soap=create_soap(subjective="患者の訴えを薬剤師が記載した。"),
        )
    )
    await fixture.medication_history_repo.save(authored_record)
    reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert reception is not None
    assert reception.source_data is not None
    original_source_data = reception.source_data
    await fixture.reception_repo.save(
        replace(reception, medication_history_id=authored_record.id)
    )
    authored_soap = authored_record.soap

    follow_up_raw = (
        "1,20260921,DOC-FOLLOWUP-LINKED,1310001,中央診療所,01,内科,佐藤医師\n"
        "2,P-1001,ヤマダタロウ,山田太郎,1,19800101\n"
    )
    bundle_follow_up = replace(
        NsipsParser().parse(follow_up_raw),
        header_version="1.0",
        correction_kind=ExternalCorrectionKind.UPDATE,
    )
    follow_up_result = await execute_structured_test_command(
        fixture,
        IngestNsipsCommand(
            corporate_id=str(fixture.corporate_id.value),
            store_id=str(fixture.store_id.value),
            reception_id=str(reception_id.value),
            expected_fingerprint=initial.source_fingerprint,
            structured_bundle=bundle_follow_up,
        ),
    )

    assert follow_up_result.is_follow_up_only is True
    assert follow_up_result.medication_history_id == str(authored_record.id.value)
    assert follow_up_result.follow_up_id is None
    assert len(fixture.medication_history_repo.items) == 1
    saved = fixture.medication_history_repo.items[authored_record.id]
    assert saved.soap == authored_soap
    updated_reception = await fixture.reception_repo.get(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        reception_id=reception_id,
    )
    assert updated_reception is not None
    assert updated_reception.medication_history_id == authored_record.id
    assert updated_reception.source_data is not None
    assert updated_reception.source_data.is_follow_up is True
    assert updated_reception.source_data_history == (original_source_data,)
    assert (
        updated_reception.source_data.bundle_json.value
        != original_source_data.bundle_json.value
    )
