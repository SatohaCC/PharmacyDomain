"""医薬品CSVのファイル読み込みと文字コードの解釈。"""

from pathlib import Path

from app.application.medicine_catalog.errors import YjCatalogParseError


def read_catalog_text(path: Path) -> str:
    """UTF-8またはCP932の原本を読み、Applicationへ文字列で渡す。"""
    if not path.exists():
        raise YjCatalogParseError(f"指定されたファイルが存在しません: {path}")
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp932")
