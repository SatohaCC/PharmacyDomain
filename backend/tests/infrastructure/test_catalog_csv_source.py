"""CSV原本の文字コード解釈を技術境界で検証する。"""

from pathlib import Path

import pytest

from app.application.medicine_catalog.errors import YjCatalogParseError
from app.infrastructure.medicine_catalog.csv_source import read_catalog_text


@pytest.mark.parametrize("encoding", ["utf-8-sig", "cp932"])
def test_CSV原本_対応する文字コードで_文字列を取得する(
    tmp_path: Path, encoding: str
) -> None:
    # Arrange
    text = "YJコード,医薬品名\n1111111F1011,テスト医薬品\n"
    path = tmp_path / "catalog.csv"
    path.write_bytes(text.encode(encoding))
    # Act
    actual = read_catalog_text(path)
    # Assert
    assert actual == text


def test_CSV原本_未存在なら_取込エラーにする(tmp_path: Path) -> None:
    # Arrange / Act / Assert
    with pytest.raises(YjCatalogParseError, match="存在しません"):
        read_catalog_text(tmp_path / "missing.csv")
