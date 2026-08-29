"""コードと通常テストが設計文書へ依存していないことを強制する。

AGENTS.md「文書とコードの分離」の実行可能版である。

**この規則だけを文章で持つことはできない。** 文書の参照は型検査にもテストにも
現れないので、破っても何も落ちない。実際、文書体系を入れ替えたときに参照が
一斉に宙へ浮いたが pytest は緑のままだった。逆に参照を全廃した直後にも、
文書を指す表記が1件だけ生き残っていた。どちらも人手の grep では取りこぼす形だった。

禁じるのは**参照の形**であって、文書に書いてある事柄ではない。理由はむしろ
docstring に書くべきで、そのとき外部を指さずその場で読めるようにする。

判定する3つの形:

1. 文書ディレクトリを含むパス（``docs/ddd/prescription.md`` など）
2. ADR番号（``ADR-13`` など）
3. 文書用の不変条件ID（``PRES-INV-001`` など）

見出し名は検査しない。現在の見出し一覧との照合では、見出しを改名・削除した瞬間に
古い参照を判定できなくなる。また、普通のドメイン語彙との区別も構文だけではできない。
機械検査は、文書を指すことが表記だけで確定する3形式に限定する。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: 走査対象。``AGENTS.md`` や ``README.md`` は文書を指してよいので含めない。
_SCANNED_ROOTS: Final[tuple[str, ...]] = ("app", "tests", "tools")

#: 設計文書の置き場。
_DOCS_ROOT: Final[str] = "docs"

#: 自分自身。禁止する形を例示として持つので走査から外す。
_SELF: Final[Path] = Path(__file__).resolve()

_DOCS_PATH_PATTERN = re.compile(
    rf"""(?<![\w.-]){re.escape(_DOCS_ROOT)}[\\/]
    (?:[^\r\n'"`<>|]*?\.md\b|[\w.-]+(?:[\\/][\w.-]+)*)?
    """,
    re.VERBOSE,
)
_ADR_PATTERN = re.compile(r"\bADR-\d+\b")
_INVARIANT_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,7}-INV-\d+\b")


def _scanned_files() -> list[Path]:
    """走査対象の Python ファイルを列挙する。"""
    return sorted(
        path
        for root in _SCANNED_ROOTS
        for path in (_REPO_ROOT / root).rglob("*.py")
        if path.resolve() != _SELF
    )


def _violations_in(line: str) -> list[str]:
    """1行に含まれる文書参照を返す。"""
    return [
        match.group(0)
        for pattern in (_DOCS_PATH_PATTERN, _ADR_PATTERN, _INVARIANT_ID_PATTERN)
        for match in pattern.finditer(line)
    ]


def _collect_violations() -> list[str]:
    """走査対象すべてから文書参照を集める。"""
    return [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{line_number} -> {reference}"
        for path in _scanned_files()
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        for reference in _violations_in(line)
    ]


def test_コードと通常テストが設計文書を参照しない() -> None:
    """文書のパス・ADR番号・不変条件IDを参照していないことを検証する。

    参照すると、文書を編集しただけでコードの説明が壊れる。壊れても型検査も
    テストも落ちないので、気づくのは次に誰かがその docstring を読んだときになる。
    """
    # Arrange / Act
    violations = _collect_violations()

    # Assert
    assert not violations, (
        "コード・テストから設計文書への参照が残っています。"
        "その場で読める言葉に書き換えてください:\n" + "\n".join(violations)
    )


def test_文書参照の安定した3形式を検出する() -> None:
    """パスの区切り文字や空白に左右されず、安定した参照構文を検出する。"""
    # Arrange
    cases = (
        ("参照: docs/ddd/prescription.md", "docs/ddd/prescription.md"),
        (r"参照: docs\ddd\prescription.md", r"docs\ddd\prescription.md"),
        ("参照: docs/設計 資料/処方概要.md", "docs/設計 資料/処方概要.md"),
        ("判断: ADR-13", "ADR-13"),
        ("規則: PRES-INV-001", "PRES-INV-001"),
    )

    for source, expected in cases:
        # Act
        violations = _violations_in(source)

        # Assert
        assert violations == [expected]


def test_見出しらしい語句だけでは文書参照と判定しない() -> None:
    """改名・削除で意味が変わる見出し文字列を検査対象にしない。"""
    # Arrange
    source = "仕様書の「すでに削除された見出し」を参照する"

    # Act
    violations = _violations_in(source)

    # Assert
    assert violations == []
