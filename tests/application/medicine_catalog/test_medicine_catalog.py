"""医薬品マスタユースケースのテスト。

このコンテキストだけが**対象法人を取らない**。薬価基準は国が定めるので
法人ごとの操作ではなく、取り込みはベンダーシステム管理者専用にしている。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.access_control import (
    ActorContext,
    AuthorizationService,
    Permission,
)
from app.application.common.exceptions import AuthorizationError
from app.application.medicine_catalog import (
    GetEffectiveMedicineQuery,
    GetEffectiveMedicineUseCase,
    MedicineNotFoundError,
    RegisterMedicineCommand,
    RegisterMedicineUseCase,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medicine_catalog import (
    MedicineEffectivePeriodConflictError,
    MedicineEffectivePeriodConflictService,
)
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)

_CODE = "2171022F1029"


def _command(
    *,
    code: str = _CODE,
    listed_on: date = date(2020, 4, 1),
    withdrawn_on: date | None = None,
    narcotic_category: str = "none",
    dosage_form: str = "tablet",
    has_dosage_limit: bool = False,
) -> RegisterMedicineCommand:
    """取り込みコマンドを組み立てる。"""
    return RegisterMedicineCommand(
        code_type="yj",
        code=code,
        name="ノルバスク錠２．５ｍｇ",
        unit="錠",
        dosage_form=dosage_form,
        listed_on=listed_on,
        withdrawn_on=withdrawn_on,
        catalog_version=date(2026, 4, 1),
        narcotic_category=narcotic_category,
        has_dosage_limit=has_dosage_limit,
    )


def _vendor_authorization() -> AuthorizationService:
    """ベンダーシステム管理者の認可コンテキスト。"""
    return AuthorizationService(
        ActorContext.vendor_system_admin(principal_id="test-vendor-admin")
    )


def _corporate_admin_authorization() -> AuthorizationService:
    """法人管理者の認可コンテキスト。"""
    return AuthorizationService(
        ActorContext.corporate_admin(
            principal_id="test-corporate-admin", corporate_id=CorporateId.generate()
        )
    )


def _register_use_case(
    repository: InMemoryMedicineCatalogRepository,
    authorization: AuthorizationService | None = None,
) -> RegisterMedicineUseCase:
    """取り込みユースケースを組み立てる。"""
    return RegisterMedicineUseCase(
        repository,
        authorization if authorization is not None else _vendor_authorization(),
        MedicineEffectivePeriodConflictService(),
    )


class Test取り込み:
    """ベンダーシステム管理者だけが行える。"""

    async def test_マスタ行を取り込める(self) -> None:
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        use_case = _register_use_case(repository)

        # Act
        actual = await use_case.execute(_command())

        # Assert
        assert actual.code == _CODE
        assert actual.listed_on == "2020-04-01"
        assert actual.withdrawn_on is None

    async def test_導出値も_あわせて返る(self) -> None:
        """呼び出し側が生の事実から判定し直すと、規則の実装が2箇所に分かれる。"""
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        use_case = _register_use_case(repository)

        # Act
        actual = await use_case.execute(
            _command(narcotic_category="narcotic", has_dosage_limit=True)
        )

        # Assert
        assert actual.is_narcotic
        assert actual.forbids_refill

    async def test_法人管理者は_取り込めない(self) -> None:
        """薬価基準の取り込みは全法人に影響するので法人管理者には許さない。"""
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        use_case = _register_use_case(repository, _corporate_admin_authorization())

        # Act / Assert
        with pytest.raises(AuthorizationError):
            await use_case.execute(_command())

    async def test_収載期間が重なると_取り込めない(self) -> None:
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        use_case = _register_use_case(repository)
        await use_case.execute(
            _command(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
        )

        # Act / Assert
        with pytest.raises(MedicineEffectivePeriodConflictError):
            await use_case.execute(_command(listed_on=date(2026, 3, 31)))

    async def test_改定で行が入れ替わる形なら_取り込める(self) -> None:
        """旧行の期限翌日から新行が始まる。隣接は重複ではない。"""
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        use_case = _register_use_case(repository)
        await use_case.execute(
            _command(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
        )

        # Act
        actual = await use_case.execute(_command(listed_on=date(2026, 4, 1)))

        # Assert
        assert actual.listed_on == "2026-04-01"

    async def test_不正な剤形は_受け付けない(self) -> None:
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        use_case = _register_use_case(repository)

        # Act / Assert
        with pytest.raises(DomainValidationError, match="剤形"):
            await use_case.execute(_command(dosage_form="unknown_form"))


class Test取得:
    """適用日で引く。"""

    async def test_適用日に有効な行が返る(self) -> None:
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        await _register_use_case(repository).execute(
            _command(listed_on=date(2020, 4, 1), withdrawn_on=date(2026, 3, 31))
        )
        await _register_use_case(repository).execute(
            _command(listed_on=date(2026, 4, 1), has_dosage_limit=True)
        )
        use_case = GetEffectiveMedicineUseCase(repository, _vendor_authorization())

        # Act
        before = await use_case.execute(
            GetEffectiveMedicineQuery(
                code_type="yj", code=_CODE, as_of=date(2026, 3, 31)
            )
        )
        after = await use_case.execute(
            GetEffectiveMedicineQuery(
                code_type="yj", code=_CODE, as_of=date(2026, 4, 1)
            )
        )

        # Assert
        assert not before.has_dosage_limit
        assert after.has_dosage_limit

    async def test_収載前の日付では_404相当になる(self) -> None:
        """「マスタに無い」と「その日には有効でない」を区別しない。"""
        # Arrange
        repository = InMemoryMedicineCatalogRepository()
        await _register_use_case(repository).execute(
            _command(listed_on=date(2026, 4, 1))
        )
        use_case = GetEffectiveMedicineUseCase(repository, _vendor_authorization())

        # Act / Assert
        with pytest.raises(MedicineNotFoundError):
            await use_case.execute(
                GetEffectiveMedicineQuery(
                    code_type="yj", code=_CODE, as_of=date(2026, 3, 31)
                )
            )


class Test権限の分類:
    """マスタ操作はベンダー専用権限に分類されている。"""

    def test_マスタ権限は_法人管理者に与えられていない(self) -> None:
        """法人管理者に与えると、1法人の操作で全法人のマスタが変わる。"""
        # Arrange
        authorization = _corporate_admin_authorization()

        # Act / Assert
        with pytest.raises(AuthorizationError):
            authorization.require_vendor_system_admin(
                permission=Permission.MANAGE_MEDICINE_CATALOG
            )
