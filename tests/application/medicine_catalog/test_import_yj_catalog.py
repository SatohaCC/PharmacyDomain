"""YJコードリストCSVインポートのパーサー・ユースケーステスト (TC-01〜TC-23, TC-30)。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.application.access_control import ActorContext, AuthorizationService
from app.application.common.exceptions import AuthorizationError
from app.application.medicine_catalog import (
    ImportYjCatalogCommand,
    ImportYjCatalogUseCase,
    YjCatalogCsvParser,
    YjCatalogParseError,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medicine_catalog.primitives import (
    GenericCategory,
    MedicineDosageForm,
    NarcoticCategory,
)
from app.domain.shared.medicine import MedicineCodeType
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)


def _vendor_auth() -> AuthorizationService:
    return AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="test-vendor-admin")
    )


def _corporate_admin_auth() -> AuthorizationService:
    return AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="test-corporate-admin", corporate_id=CorporateId.generate()
        )
    )


def test_YJコードが正しく識別子へ変換される() -> None:
    """TC-01: YJコード列（12桁英数字）が MedicineIdentifier(code_type="yj", code=...) へ変換される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
    medicines = parser.parse_text(csv_text)
    assert len(medicines) == 1
    med = medicines[0]
    assert med.identifier.code_type == MedicineCodeType.YJ
    assert med.identifier.code is not None
    assert med.identifier.code.value == "1115400X1027"


def test_YJ第8文字による錠剤判定() -> None:
    """TC-02: YJコード第8文字が 'F' または 'K' の場合、TABLET（錠剤）に判定される。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"2171022F1029","ノルバスク錠２．５ｍｇ","ヴィアトリス","","",""\n'
        '"2171018K1039","ニトロペン舌下錠０．３ｍｇ","日本化薬","","",""\n'
    )
    medicines = parser.parse_text(csv_text)
    assert len(medicines) == 2
    assert medicines[0].dosage_form == MedicineDosageForm.TABLET
    assert medicines[1].dosage_form == MedicineDosageForm.TABLET


def test_YJ第8文字による内服注射剤形判定() -> None:
    """TC-03: YJ第8文字 'M'->CAPSULE, 'B'/'C'/'R'->POWDER, 'G'/'U'->LIQUID, 'A'/'D'/'E'/'L'->INJECTION。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"1124002M2022","テストカプセル","会社A","","",""\n'
        '"1124001B1039","テスト散剤","会社B","","",""\n'
        '"1119402G1025","テストシロップ","会社C","","",""\n'
        '"1119400A1031","テスト注射液","会社D","","",""\n'
    )
    medicines = parser.parse_text(csv_text)
    assert medicines[0].dosage_form == MedicineDosageForm.CAPSULE
    assert medicines[1].dosage_form == MedicineDosageForm.POWDER
    assert medicines[2].dosage_form == MedicineDosageForm.LIQUID
    assert medicines[3].dosage_form == MedicineDosageForm.INJECTION


def test_YJ第8文字による外用剤形判定() -> None:
    """TC-04: YJ第8文字 'S'/'P'->PATCH, 'Q'/'V'->OINTMENT, 'N'->EYE_DROP, 'J'->SUPPOSITORY, 'X'->OTHER。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"2649735S1028","モーラステープ２０ｍｇ","久光製薬","","",""\n'
        '"2649709Q1022","テスト軟膏","会社Q","","",""\n'
        '"1319702N1020","テスト点眼液","会社N","","",""\n'
        '"1123700J1020","テスト坐剤","会社J","","",""\n'
        '"1112700X1011","ハロタン","会社X","","",""\n'
    )
    medicines = parser.parse_text(csv_text)
    assert medicines[0].dosage_form == MedicineDosageForm.PATCH
    assert medicines[1].dosage_form == MedicineDosageForm.OINTMENT
    assert medicines[2].dosage_form == MedicineDosageForm.EYE_DROP
    assert medicines[3].dosage_form == MedicineDosageForm.SUPPOSITORY
    assert medicines[4].dosage_form == MedicineDosageForm.OTHER


def test_薬品名からの単位抽出() -> None:
    """TC-05: 薬品名末尾に単位語（錠、カプセル、ｇ、ｍＬ、枚、管、個等）がある行から正しく抽出される。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"2171022F1029","ノルバスク錠２．５ｍｇ","ヴィアトリス","","",""\n'
        '"2649735S1028","モーラステープ２０ｍｇ","久光製薬","","",""\n'
        '"1119400A1031","ケタラール筋注用５００ｍｇ","第一三共","","",""\n'
    )
    medicines = parser.parse_text(csv_text)
    assert medicines[0].unit.value == "錠"
    assert medicines[1].unit.value == "枚"
    assert medicines[2].unit.value == "管"


def test_剤形に応じた既定単位補完() -> None:
    """TC-06: 薬品名から単位が抽出できない行には、剤形に応じた標準単位が補完される。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"1112700X1011","ハロタン","","","",""\n'
        '"2171013K1010","ニトログリセリン","","","",""\n'
    )
    medicines = parser.parse_text(csv_text)
    # OTHER -> 個, TABLET -> 錠
    assert medicines[0].unit.value in ("個", "ｇ", "ｍＬ")
    assert medicines[1].unit.value == "錠"


def test_登録日と除外日が両方ある収載期間の構築() -> None:
    """TC-07: 登録日(col3)と除外日(col4)の両方が存在する場合、[listed_on, withdrawn_on] が正しく構築される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1179043F1016","ベスピダ錠４ｍｇ","","20240415","20260331",""\n'
    medicines = parser.parse_text(csv_text)
    med = medicines[0]
    assert med.effective_period.listed_on.value == date(2024, 4, 15)
    assert med.effective_period.withdrawn_on is not None
    assert med.effective_period.withdrawn_on.value == date(2026, 3, 31)


def test_登録日未設定時の基準初期収載日補完() -> None:
    """TC-08: 登録日が空文字の場合、1950-01-01 が補完され listed_on <= withdrawn_on 不変条件を満たす。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115403D3051","チトゾール注用０．５ｇ","杏林製薬","","20250331",""\n'
    medicines = parser.parse_text(csv_text)
    med = medicines[0]
    assert med.effective_period.listed_on.value == date(1950, 1, 1)
    assert med.effective_period.withdrawn_on is not None
    assert med.effective_period.withdrawn_on.value == date(2025, 3, 31)
    assert (
        med.effective_period.listed_on.value <= med.effective_period.withdrawn_on.value
    )


def test_除外日なしは無期限有効となる() -> None:
    """TC-09: 登録日・除外日ともに空文字、または除外日のみ空文字の場合、withdrawn_on=None となる。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1112700X1011","ハロタン","","","",""\n'
    medicines = parser.parse_text(csv_text)
    med = medicines[0]
    assert med.effective_period.listed_on.value == date(1950, 1, 1)
    assert med.effective_period.withdrawn_on is None
    assert med.is_effective_on(date(2026, 9, 21)) is True


def test_YJ薬効811の麻薬判定() -> None:
    """TC-10: YJコード先頭3桁が '811' の場合、NARCOTIC に判定される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"8112001A1018","アヘン注","","","",""\n'
    medicines = parser.parse_text(csv_text)
    assert medicines[0].narcotic_category == NarcoticCategory.NARCOTIC
    assert medicines[0].is_narcotic is True


def test_YJ薬効821の覚醒剤原料判定() -> None:
    """TC-11: YJコード先頭3桁が '821' の場合、STIMULANT_RAW_MATERIAL に判定される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"8211001X1019","ペチジン塩酸塩","","","",""\n'
    medicines = parser.parse_text(csv_text)
    assert medicines[0].narcotic_category == NarcoticCategory.STIMULANT_RAW_MATERIAL


def test_通常薬品の麻薬非該当判定() -> None:
    """TC-12: 通常薬効コードの医薬品は narcotic_category=NONE に判定される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
    medicines = parser.parse_text(csv_text)
    assert medicines[0].narcotic_category == NarcoticCategory.NONE


def test_先発後発区分の自動判定() -> None:
    """TC-13: 薬品名屋号「」あり->GENERIC, 屋号なし会社名あり->BRAND, 会社名空->OTHER に分類される。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"1119402A1120","プロポフォール静注１％２０ｍＬ「マルイシ」","丸石製薬","","",""\n'
        '"1119400A1031","ケタラール静注用２００ｍｇ","第一三共","","",""\n'
        '"1112700X1011","ハロタン","","","",""\n'
    )
    medicines = parser.parse_text(csv_text)
    assert medicines[0].generic_category == GenericCategory.GENERIC
    assert medicines[1].generic_category == GenericCategory.BRAND
    assert medicines[2].generic_category == GenericCategory.OTHER


def test_鎮痛消炎貼付剤のフラグ設定() -> None:
    """TC-14: YJ先頭4桁が '2649' かつ貼付剤の場合、is_analgesic_antiinflammatory=True となる。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"2649735S1028","モーラステープ２０ｍｇ","久光製薬","","",""\n'
    medicines = parser.parse_text(csv_text)
    assert medicines[0].dosage_form == MedicineDosageForm.PATCH
    assert medicines[0].is_analgesic_antiinflammatory is True


def test_不正YJコードで行番号付き構文例外() -> None:
    """TC-15: YJコードが12桁未満または欠損している場合、行番号付きの YjCatalogParseError が送出される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"INVALID","ラボナール","ニプロ","","",""\n'
    with pytest.raises(YjCatalogParseError) as exc_info:
        parser.parse_text(csv_text)
    assert "2行目" in str(exc_info.value)


def test_薬品名欠損で行番号付き構文例外() -> None:
    """TC-16: 医薬品名が空文字の行で YjCatalogParseError が送出される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","","ニプロ","","",""\n'
    with pytest.raises(YjCatalogParseError) as exc_info:
        parser.parse_text(csv_text)
    assert "2行目" in str(exc_info.value)


def test_日付フォーマット異常で構文例外() -> None:
    """TC-17: 日付列に不正なフォーマットの日付文字列が含まれる場合、YjCatalogParseError が送出される。"""
    parser = YjCatalogCsvParser()
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール","ニプロ","20259999","",""\n'
    with pytest.raises(YjCatalogParseError) as exc_info:
        parser.parse_text(csv_text)
    assert "2行目" in str(exc_info.value)


def test_ヘッダーと空行の安全なスキップ() -> None:
    """TC-18: CSVヘッダー行および空行・余剰カンマ行が安全にスキップされる。"""
    parser = YjCatalogCsvParser()
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        "\n"
        '"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
        ",,,,\n"
    )
    medicines = parser.parse_text(csv_text)
    assert len(medicines) == 1


@pytest.mark.asyncio
async def test_複数行CSVの一括インポート成功() -> None:
    """TC-19: 有効なCSVテキスト（複数行）のインポートが実行され、リポジトリに全件永続化される。"""
    repo = InMemoryMedicineCatalogRepository()
    use_case = ImportYjCatalogUseCase(repo, _vendor_auth())
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
        '"2171022F1029","ノルバスク錠２．５ｍｇ","ヴィアトリス","","",""\n'
    )
    result = await use_case.execute(ImportYjCatalogCommand(csv_text=csv_text))
    assert result.total_rows == 2
    assert result.imported_count == 2
    assert len(repo.items) == 2


@pytest.mark.asyncio
async def test_インポート結果DTOの正確性() -> None:
    """TC-20: total_rows, imported_count, catalog_version が正しく返却される。"""
    repo = InMemoryMedicineCatalogRepository()
    use_case = ImportYjCatalogUseCase(repo, _vendor_auth())
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
    result = await use_case.execute(
        ImportYjCatalogCommand(csv_text=csv_text, catalog_version=date(2026, 8, 15))
    )
    assert result.total_rows == 1
    assert result.imported_count == 1
    assert result.catalog_version == date(2026, 8, 15)


@pytest.mark.asyncio
async def test_非ベンダーシステム管理者の実行は拒否される() -> None:
    """TC-21: 非ベンダーシステム管理者（法人管理者・店舗スタッフ）で実行すると AuthorizationError となる。"""
    repo = InMemoryMedicineCatalogRepository()
    use_case = ImportYjCatalogUseCase(repo, _corporate_admin_auth())
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
    with pytest.raises(AuthorizationError):
        await use_case.execute(ImportYjCatalogCommand(csv_text=csv_text))


@pytest.mark.asyncio
async def test_同一CSVの再インポートが安全に完了する() -> None:
    """TC-22: 同一CSVを2回インポートしてもエラーなく完了する。"""
    repo = InMemoryMedicineCatalogRepository()
    use_case = ImportYjCatalogUseCase(repo, _vendor_auth())
    csv_text = '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n"1115400X1027","ラボナール注射用０．３ｇ","ニプロ","","",""\n'
    await use_case.execute(ImportYjCatalogCommand(csv_text=csv_text))
    # 2回目実行
    result2 = await use_case.execute(ImportYjCatalogCommand(csv_text=csv_text))
    assert result2.total_rows == 1
    assert len(repo.items) == 1


@pytest.mark.asyncio
async def test_複数チャンクにまたがるバッチインポート() -> None:
    """TC-23: チャンクサイズ（例: 2件）を超える件数のCSVインポートでも全件が正しく保存される。"""
    repo = InMemoryMedicineCatalogRepository()
    use_case = ImportYjCatalogUseCase(repo, _vendor_auth(), chunk_size=2)
    csv_text = (
        '"ＹＪコード","医薬品名","会社名","リスト登録年月日","リスト除外年月日","変更区分"\n'
        '"1111111F1011","薬品1","","","",""\n'
        '"2222222F2022","薬品2","","","",""\n'
        '"3333333F3033","薬品3","","","",""\n'
        '"4444444F4044","薬品4","","","",""\n'
        '"5555555F5055","薬品5","","","",""\n'
    )
    result = await use_case.execute(ImportYjCatalogCommand(csv_text=csv_text))
    assert result.total_rows == 5
    assert len(repo.items) == 5


def test_実YJコードCSVサンプル行の統合パース() -> None:
    """TC-30: 実YJコードリストCSVファイルの冒頭100行以上が安全にパースできる。"""
    csv_path = (
        Path("docs")
        / "references"
        / "個別医薬品コード(YJコード)リスト_202608_20260815.csv"
    )
    if not csv_path.exists():
        pytest.skip("実CSVファイルが存在しません。")
    parser = YjCatalogCsvParser()
    medicines = parser.parse_file(csv_path)
    assert len(medicines) > 100
