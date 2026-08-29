"""医薬品マスタと処方箋の規制判定をつなぐ実アダプタのテスト。

このアダプタが**腐敗防止層**であることを固定する。マスタが持つのは剤形・効能・
麻薬区分といった事実で、処方箋が要るのは「リフィル適用除外か」という規則の答え。
形が違うので変換が要り、その変換をここに閉じ込めている。
"""

from __future__ import annotations

from datetime import date

from app.application.composition import MedicineCatalogRestrictionAdapter
from app.domain.medicine_catalog import Medicine, NarcoticCategory
from app.domain.prescription import MedicineRestrictionFlag
from tests.factories.medicine_catalog_factory import (
    create_identifier,
    create_medicine,
    create_refill_restricted_patch,
)
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)

_AS_OF = date(2026, 8, 24)


async def _adapter_with(*medicines: Medicine) -> MedicineCatalogRestrictionAdapter:
    """マスタへ登録済みのアダプタを組み立てる。"""
    repository = InMemoryMedicineCatalogRepository()
    for medicine in medicines:
        await repository.save(medicine)
    return MedicineCatalogRestrictionAdapter(repository)


class Test事実から規則の答えへの変換:
    """アダプタが導出を担う。"""

    async def test_通常の薬品は_どの区分にも該当しない(self) -> None:
        # Arrange
        adapter = await _adapter_with(create_medicine())
        identifier = create_identifier()

        # Act
        actual = await adapter.classify(identifiers=(identifier,), as_of=_AS_OF)

        # Assert
        classification = actual[identifier]
        assert classification.is_narcotic is MedicineRestrictionFlag.NO
        assert classification.has_dosage_limit is MedicineRestrictionFlag.NO
        assert not classification.forbids_refill

    async def test_麻薬は_麻薬区分が該当になる(self) -> None:
        # Arrange
        adapter = await _adapter_with(
            create_medicine(narcotic_category=NarcoticCategory.NARCOTIC)
        )
        identifier = create_identifier()

        # Act
        actual = await adapter.classify(identifiers=(identifier,), as_of=_AS_OF)

        # Assert
        assert actual[identifier].is_narcotic is MedicineRestrictionFlag.YES

    async def test_鎮痛消炎の貼付剤は_リフィル不可として返る(self) -> None:
        """マスタの4つの事実（剤形・効能・麻薬区分・皮膚疾患用）から導出する。"""
        # Arrange
        patch = create_refill_restricted_patch()
        adapter = await _adapter_with(patch)
        identifier = patch.identifier

        # Act
        actual = await adapter.classify(identifiers=(identifier,), as_of=_AS_OF)

        # Assert
        classification = actual[identifier]
        assert classification.is_refill_restricted_patch is MedicineRestrictionFlag.YES
        assert classification.forbids_refill

    async def test_麻薬の貼付剤は_貼付剤の除外に当たらない(self) -> None:
        """括弧内の除外がアダプタを通っても保たれることを固定する。"""
        # Arrange
        patch = create_refill_restricted_patch(
            narcotic_category=NarcoticCategory.NARCOTIC
        )
        adapter = await _adapter_with(patch)

        # Act
        actual = await adapter.classify(identifiers=(patch.identifier,), as_of=_AS_OF)

        # Assert
        classification = actual[patch.identifier]
        assert classification.is_refill_restricted_patch is MedicineRestrictionFlag.NO
        assert classification.is_narcotic is MedicineRestrictionFlag.YES


class Test適用日:
    """時点で答えが変わる。"""

    async def test_改定の前後で_返る規制区分が変わる(self) -> None:
        """「今」で引く実装だと、過去の処方を新しいマスタで判定してしまう。"""
        # Arrange
        adapter = await _adapter_with(
            create_medicine(
                listed_on=date(2020, 4, 1),
                withdrawn_on=date(2026, 3, 31),
                has_dosage_limit=False,
            ),
            create_medicine(listed_on=date(2026, 4, 1), has_dosage_limit=True),
        )
        identifier = create_identifier()

        # Act
        before = await adapter.classify(
            identifiers=(identifier,), as_of=date(2026, 3, 31)
        )
        after = await adapter.classify(
            identifiers=(identifier,), as_of=date(2026, 4, 1)
        )

        # Assert
        assert before[identifier].has_dosage_limit is MedicineRestrictionFlag.NO
        assert after[identifier].has_dosage_limit is MedicineRestrictionFlag.YES


class Test未収載の扱い:
    """fail-closedがアダプタでも保たれること。"""

    async def test_マスタに無い薬品は_戻り値に含めない(self) -> None:
        """「該当しない」既定値で埋めると、未収載の薬品で判定が素通りする。"""
        # Arrange
        adapter = await _adapter_with()

        # Act
        actual = await adapter.classify(
            identifiers=(create_identifier(),), as_of=_AS_OF
        )

        # Assert
        assert actual == {}

    async def test_経過措置切れの薬品も_戻り値に含めない(self) -> None:
        """「マスタに無い」と「その日には有効でない」を同じ扱いにする。"""
        # Arrange
        adapter = await _adapter_with(
            create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
        )

        # Act
        actual = await adapter.classify(
            identifiers=(create_identifier(),), as_of=date(2026, 4, 1)
        )

        # Assert
        assert actual == {}

    async def test_一部だけ引ければ_引けた分だけ返る(self) -> None:
        """欠落の検出は呼び出し側の Domain Service が行う。"""
        # Arrange
        known = create_medicine()
        adapter = await _adapter_with(known)
        unknown = create_identifier("1124017F1030")

        # Act
        actual = await adapter.classify(
            identifiers=(known.identifier, unknown), as_of=_AS_OF
        )

        # Assert
        assert set(actual) == {known.identifier}
