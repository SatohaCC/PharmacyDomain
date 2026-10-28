"""Applicationのget_last_coverage_selectionを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.coverage.queries.dtos.get_coverage_selection import (
    CoverageSelectionRecordDto,
)


@dataclass(frozen=True, kw_only=True)
class LastCoverageSelectionCandidateDto:
    """最新履歴と今回の適用日における真正性。"""

    record: CoverageSelectionRecordDto
    is_still_valid: bool
