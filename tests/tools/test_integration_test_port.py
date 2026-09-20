"""AGENTS.md の結合テストコマンド例が実際に接続できる形になっていることを強制する。

`compose.yaml` はホスト側の公開ポートを `.env` の `POSTGRES_PORT`（既定 5432）に
従わせている。AGENTS.md のコマンド例が `5432` のような固定のポート番号を書いていると、
`POSTGRES_PORT` を変えている開発機（他プロジェクトとのポート衝突を避けるため
上書きしている環境など）でそのコマンド例をそのまま実行したときに接続エラーになる。
`TEST_DATABASE_URL` が無いときは結合テストが自動でスキップされるだけだが、
ポートを間違えたまま接続を試みると `ConnectionRefusedError` という例外になるので
「気づけない」わけではない。ただし気づいた時点で作業の手が止まってしまうので、
文章の規約だけに頼らずここで機械的に検査する。

**`POSTGRES_PORT` を参照しているだけでは足りない。** シェルは `.env` を自動で
読み込まない（読むのは `docker compose` 自身だけ）ので、コマンド例が
`${POSTGRES_PORT:-5432}` と書いていても、その手前で `.env` を明示的に読み込む行が
無ければ環境変数 `POSTGRES_PORT` は未設定のままで、結局は既定値 5432 に落ちる。
これは「`POSTGRES_PORT` を参照しているか」という行単位の検査だけでは検出できない
欠陥だった（参照はしているが、参照先の変数が実際には空だった）。そこで
`TEST_DATABASE_URL=` を含む行が属する bash コードブロック全体を見て、
`.env` を読み込む行を伴っているかまで検査する。

`tests/tools/test_ci_quality_gate.py` が AGENTS.md をテキストとして読み込んで
検査する書き方に合わせ、ここでも AGENTS.md をそのまま読み込んで判定する。
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_MD = _ROOT / "AGENTS.md"

# ホストへポート番号を直接書いている形（例: @127.0.0.1:5432）を検出する。
# `${POSTGRES_PORT:-5432}` のように `$` を挟む場合はコロンの直後が `$` になるため
# この形にはマッチしない。
_HARDCODED_PORT_PATTERN = re.compile(r"@127\.0\.0\.1:\d+")

# `. ./.env` や `source .env` のように `.env` をシェルへ読み込む（dot-source する）
# 行を検出する。単に文字列 `.env` が本文に出てくるだけ（`[ -f .env ]` のような
# 存在チェックなど）では拾わないよう、コマンドの先頭に `.` または `source` が
# 来る形に限定する。
_ENV_LOAD_PATTERN = re.compile(r"(?:^|[\s;&|])(?:\.|source)\s+\S*\.env\b", re.MULTILINE)

# ```bash ... ``` フェンスの本文を取り出す。
_BASH_BLOCK_PATTERN = re.compile(r"```bash\n(.*?)```", re.DOTALL)


def _bash_code_blocks() -> list[str]:
    """AGENTS.md 中の ```bash コードブロックの本文を全て取り出す。"""
    text = _AGENTS_MD.read_text(encoding="utf-8")
    return _BASH_BLOCK_PATTERN.findall(text)


def _bash_blocks_with_test_database_url() -> list[str]:
    """`TEST_DATABASE_URL=` を含む bash コードブロックだけを取り出す。"""
    return [block for block in _bash_code_blocks() if "TEST_DATABASE_URL=" in block]


def _test_database_url_lines() -> list[str]:
    """AGENTS.md から `TEST_DATABASE_URL=` を含む行を取り出す。"""
    text = _AGENTS_MD.read_text(encoding="utf-8")
    return [line for line in text.splitlines() if "TEST_DATABASE_URL=" in line]


def test_AGENTSmd_TEST_DATABASE_URLを含む行が1件以上見つかる() -> None:
    """探索が壊れたときに、無検査で緑になるのを防ぐ。"""
    # Act
    lines = _test_database_url_lines()

    # Assert
    assert lines, "AGENTS.md に `TEST_DATABASE_URL=` を含む行が無い"


def test_結合テストのコマンド例がPOSTGRES_PORTを参照している() -> None:
    """接続ポートは `.env` の `POSTGRES_PORT` に従うので、コマンド例もそこから引く。

    `POSTGRES_PORT` を参照していないコマンド例は、`compose.yaml` が実際に公開する
    ポートと無関係な値になりうる。
    """
    # Arrange
    lines = _test_database_url_lines()

    # Act
    missing = [line for line in lines if "POSTGRES_PORT" not in line]

    # Assert
    assert not missing, f"POSTGRES_PORT を参照していない行がある: {missing}"


def test_結合テストのコマンド例がポート番号をベタ書きしていない() -> None:
    """`@127.0.0.1:5432` のような固定ポートの書き方を禁止する。

    ベタ書きすると、`POSTGRES_PORT` を変えている環境でこのコマンド例をそのまま
    実行したときに接続エラーになり、既定構成の環境しか動作確認できていない
    コマンド例が正典として残ってしまう。
    """
    # Arrange
    lines = _test_database_url_lines()

    # Act
    hardcoded = [line for line in lines if _HARDCODED_PORT_PATTERN.search(line)]

    # Assert
    assert not hardcoded, f"ポート番号をベタ書きしている行がある: {hardcoded}"


def test_AGENTSmd_TEST_DATABASE_URLを含むbashブロックが1件見つかる() -> None:
    """探索が壊れたときに、無検査で緑になるのを防ぐ。"""
    # Act
    blocks = _bash_blocks_with_test_database_url()

    # Assert
    assert len(blocks) == 1, f"該当ブロックが1件に定まらない: {len(blocks)}件"


def test_結合テストのコマンド例が_envを読み込んでからPOSTGRES_PORTを使う() -> None:
    """`POSTGRES_PORT` を参照しているだけでは、値が入っているとは限らない。

    シェルは `.env` を自動で読み込まないので、コマンド例が `${POSTGRES_PORT:-5432}`
    と書いていても `.env` を明示的に読み込む行が無ければ `POSTGRES_PORT` は未設定の
    ままになり、`.env` でポートを上書きしている環境でも既定値 5432 に落ちてしまう
    （＝参照はしているのにベタ書きと同じ結果になる）。行単位で「`POSTGRES_PORT` を
    含むか」だけを見る検査はこの欠陥を見逃すため、`TEST_DATABASE_URL=` を含む行が
    属する bash コードブロック全体に `.env` を読み込む行が伴っていることまで確認する。
    """
    # Arrange
    blocks = _bash_blocks_with_test_database_url()

    # Act
    missing = [block for block in blocks if not _ENV_LOAD_PATTERN.search(block)]

    # Assert
    assert not missing, f"`.env` を読み込む行が無いコマンド例がある: {missing}"
