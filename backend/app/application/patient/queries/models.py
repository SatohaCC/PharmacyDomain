"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GetPatientQuery:
    """患者詳細取得の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str


@dataclass(frozen=True, kw_only=True)
class GetPatientExternalIdentifierQuery:
    """外部患者ID対応付け取得の入力データ（DTO）。"""

    corporate_id: str
    identifier_id: str


@dataclass(frozen=True, kw_only=True)
class GetPatientHeadingQuery:
    """患者頭書き参照の入力。"""

    corporate_id: str
    patient_id: str


@dataclass(frozen=True, kw_only=True)
class ListPatientExternalIdentifiersQuery:
    """患者の外部患者ID一覧取得の入力データ（DTO）。"""

    corporate_id: str
    patient_id: str
