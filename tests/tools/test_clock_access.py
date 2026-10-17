"""時計注入の保証をRuffの採用ルールから独立させる。"""

from pathlib import Path

import pytest

from tools.check_clock_access import check_paths, find_ambient_clock_calls


@pytest.mark.parametrize(
    "source",
    [
        "from datetime import date\ndate.today()",
        "from datetime import datetime as D\nD.now()",
        "from datetime import datetime, UTC\ndatetime.now(UTC)",
        "import datetime as dt\ndt.datetime.utcnow()",
        "import datetime as dt\ndt.date.today()",
        "from time import time as current\ncurrent()",
    ],
)
def test_環境日時_業務層から直接取得すると_違反を検出する(source: str) -> None:
    assert find_ambient_clock_calls(source) == (2,)


def test_業務日時_時計注入と明示値を使うと_許可する() -> None:
    source = "from datetime import date\ndate(2026, 10, 17)\nclock.now()"
    assert find_ambient_clock_calls(source) == ()


def test_業務層_現在時刻の取得を_外側の時計へ委譲する() -> None:
    assert check_paths(Path(__file__).resolve().parents[2]) == ()
