"""Shared Kernel の順位規則テスト。

この規則は資格台帳側の ``CoverageCombination`` と請求側の ``CoverageSnapshot``
の双方が使う唯一の実装なので、境界条件はここで固定する。
"""

from __future__ import annotations

import pytest

from app.base.domain.priority_rules import PriorityViolation, find_priority_violation


@pytest.mark.parametrize(
    "priorities",
    [(), (1,), (1, 2), (1, 2, 3), (1, 2, 3, 4), (3, 1, 2), (4, 3, 2, 1)],
)
def test_順位規則_第一順位から連続していれば_違反にならない(
    priorities: tuple[int, ...],
) -> None:
    # Arrange / Act
    actual = find_priority_violation(priorities, maximum=4)

    # Assert: 並び順は問わない
    assert actual is None


def test_順位規則_上限を超える件数だと_件数超過になる() -> None:
    # Arrange / Act
    actual = find_priority_violation((1, 2, 3, 4, 5), maximum=4)

    # Assert
    assert actual is PriorityViolation.EXCEEDS_MAXIMUM


@pytest.mark.parametrize("priorities", [(1, 1), (1, 2, 2), (2, 1, 2)])
def test_順位規則_同じ順位が複数あると_重複になる(
    priorities: tuple[int, ...],
) -> None:
    # Arrange / Act
    actual = find_priority_violation(priorities, maximum=4)

    # Assert
    assert actual is PriorityViolation.DUPLICATED


@pytest.mark.parametrize("priorities", [(2,), (3,), (1, 3), (2, 3), (1, 2, 4)])
def test_順位規則_第一順位から連続していないと_欠番になる(
    priorities: tuple[int, ...],
) -> None:
    # Arrange / Act
    actual = find_priority_violation(priorities, maximum=4)

    # Assert
    assert actual is PriorityViolation.NOT_CONSECUTIVE


def test_順位規則_件数超過は重複より先に判定される() -> None:
    # Arrange / Act
    # 件数超過と重複の両方に該当する入力。上限違反を先に返すことで、
    # 「まず入る件数か」を利用側が最初に案内できる。
    actual = find_priority_violation((1, 1, 1, 1, 1), maximum=4)

    # Assert
    assert actual is PriorityViolation.EXCEEDS_MAXIMUM
