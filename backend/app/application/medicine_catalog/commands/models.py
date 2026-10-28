"""Applicationのmodelsを定義する。"""

from __future__ import annotations

from datetime import date

from app.domain.medicine_catalog.primitives import (
    MedicineDosageForm,
)

DEFAULT_CATALOG_VERSION = date(2026, 8, 15)
DEFAULT_LISTED_ON = date(1950, 1, 1)
_DOSAGE_FORM_BY_CHAR: dict[str, MedicineDosageForm] = {
    "F": MedicineDosageForm.TABLET,
    "K": MedicineDosageForm.TABLET,
    "M": MedicineDosageForm.CAPSULE,
    "B": MedicineDosageForm.POWDER,
    "C": MedicineDosageForm.POWDER,
    "R": MedicineDosageForm.POWDER,
    "G": MedicineDosageForm.LIQUID,
    "U": MedicineDosageForm.LIQUID,
    "A": MedicineDosageForm.INJECTION,
    "D": MedicineDosageForm.INJECTION,
    "E": MedicineDosageForm.INJECTION,
    "L": MedicineDosageForm.INJECTION,
    "S": MedicineDosageForm.PATCH,
    "P": MedicineDosageForm.PATCH,
    "Q": MedicineDosageForm.OINTMENT,
    "V": MedicineDosageForm.OINTMENT,
    "N": MedicineDosageForm.EYE_DROP,
    "J": MedicineDosageForm.SUPPOSITORY,
    "X": MedicineDosageForm.OTHER,
    "Y": MedicineDosageForm.OTHER,
    "H": MedicineDosageForm.OTHER,
    "T": MedicineDosageForm.OTHER,
    "W": MedicineDosageForm.OTHER,
}
_DEFAULT_UNIT_BY_DOSAGE_FORM: dict[MedicineDosageForm, str] = {
    MedicineDosageForm.TABLET: "錠",
    MedicineDosageForm.CAPSULE: "カプセル",
    MedicineDosageForm.POWDER: "ｇ",
    MedicineDosageForm.LIQUID: "ｍＬ",
    MedicineDosageForm.INJECTION: "管",
    MedicineDosageForm.PATCH: "枚",
    MedicineDosageForm.OINTMENT: "ｇ",
    MedicineDosageForm.EYE_DROP: "ｍＬ",
    MedicineDosageForm.SUPPOSITORY: "個",
    MedicineDosageForm.OTHER: "個",
}
