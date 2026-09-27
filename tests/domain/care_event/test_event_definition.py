"""標準・法人独自イベント種別の不変条件。"""

from __future__ import annotations

import pytest

from app.domain.care_event.event_definition import EventDefinition
from app.domain.care_event.primitives import EventTypeName, EventTypeStandardCode
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainError


def test_tc45_02_法人独自種別を改名してもIDと法人を保つ() -> None:
    corporate_id = CorporateId.generate()
    original = EventDefinition.create_custom(
        corporate_id=corporate_id,
        name=EventTypeName("服薬状況の相談"),
    )

    renamed = original.rename(EventTypeName("服薬継続の相談"))

    assert renamed.id == original.id
    assert renamed.corporate_id == corporate_id
    assert renamed.name.value == "服薬継続の相談"
    assert renamed.is_active
    assert original.name.value == "服薬状況の相談"


def test_tc45_03_標準種別は改名と無効化を拒否する() -> None:
    standard = EventDefinition.create_standard(
        code=EventTypeStandardCode("prescription_reception"),
        name=EventTypeName("処方箋受付"),
    )

    with pytest.raises(DomainError):
        standard.rename(EventTypeName("任意の表示名"))
    with pytest.raises(DomainError):
        standard.deactivate()


def test_tc45_04_空の法人独自種別名を拒否する() -> None:
    with pytest.raises(DomainError):
        EventDefinition.create_custom(
            corporate_id=CorporateId.generate(),
            name=EventTypeName("  "),
        )
