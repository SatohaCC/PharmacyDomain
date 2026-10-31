"""Applicationのget_effective_policy DTOを定義する。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class EffectivePolicyItemDto:
    """単一ポリシー項目の実効値と解決元。"""

    value: bool
    source: Literal["corporate", "store"]


@dataclass(frozen=True, kw_only=True)
class EffectivePolicyDto:
    """店舗の実効ポリシー投影。"""

    require_prescription_audit: EffectivePolicyItemDto
    prohibit_self_verification: EffectivePolicyItemDto
