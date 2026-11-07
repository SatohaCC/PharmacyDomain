"""NSIPSファイル名解析の単体テスト。"""

from __future__ import annotations

import pytest

from app.application.integration.boundary_models import NsipsOperation
from app.application.integration.commands.services.file_name import (
    UnknownNsipsFileNameError,
    parse_nsips_file_name,
)


def test_ファイル名解析_Aプレフィックス_create操作とfile_idを正しく抽出する() -> None:
    """A_<file_id>.<ext> は CREATE 操作として判定される。"""
    parsed = parse_nsips_file_name("A_20260726-001.xml")
    assert parsed.operation == NsipsOperation.CREATE
    assert parsed.file_id == "20260726-001"
    assert parsed.is_bulk is False


def test_ファイル名解析_Uプレフィックス_update操作を正しく抽出する() -> None:
    """U_<file_id>.<ext> は UPDATE 操作として判定される。"""
    parsed = parse_nsips_file_name("U_REC-2026-999.csv")
    assert parsed.operation == NsipsOperation.UPDATE
    assert parsed.file_id == "REC-2026-999"
    assert parsed.is_bulk is False


def test_ファイル名解析_Dプレフィックス_delete操作を正しく抽出する() -> None:
    """D_<file_id>.<ext> は DELETE 操作として判定される。"""
    parsed = parse_nsips_file_name("D_20260726-001.txt")
    assert parsed.operation == NsipsOperation.DELETE
    assert parsed.file_id == "20260726-001"
    assert parsed.is_bulk is False


def test_ファイル名解析_Bプレフィックス_is_bulkフラグ付きのcreate操作として抽出する() -> (
    None
):
    """B_<file_id>.<ext> は is_bulk=True の CREATE 操作として判定される。"""
    parsed = parse_nsips_file_name("B_BATCH-001.dat")
    assert parsed.operation == NsipsOperation.CREATE
    assert parsed.file_id == "BATCH-001"
    assert parsed.is_bulk is True


def test_ファイル名解析_ハイフン区切りと小文字プレフィックス_正常に解析される() -> None:
    """a-12345.json のように小文字やハイフン区切りでも判定できる。"""
    parsed = parse_nsips_file_name("a-12345.json")
    assert parsed.operation == NsipsOperation.CREATE
    assert parsed.file_id == "12345"


def test_ファイル名解析_未知の操作文字_エラーとなる() -> None:
    """Z_... のような未定義の操作文字は UnknownNsipsFileNameError となる。"""
    with pytest.raises(
        UnknownNsipsFileNameError, match="操作文字 'Z' を判定できません"
    ):
        parse_nsips_file_name("Z_20260726-001.xml")


def test_ファイル名解析_不正な書式_エラーとなる() -> None:
    """想定パターンに一致しないファイル名は UnknownNsipsFileNameError となる。"""
    with pytest.raises(UnknownNsipsFileNameError, match="想定パターンに一致しません"):
        parse_nsips_file_name("invalid_file_name.pdf")
