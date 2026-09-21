"""区分カタログ取得・更新ユースケースのテスト。"""

from __future__ import annotations

import pytest

from app.application.corporate.exceptions import CorporateInactiveError
from app.application.medication_history import (
    GetCategoryCatalogUseCase,
    MajorCategoryInput,
    MediumCategoryInput,
    UpdateCategoryCatalogCommand,
    UpdateCategoryCatalogUseCase,
)
from app.domain.corporate.primitives import CorporateId
from tests.application.access_helpers import (
    AutoProvisioningCorporateRepository,
    create_vendor_corporate_access_for,
)
from tests.fakes.in_memory_medication_history_repository import (
    InMemoryMedicationHistoryCategoryCatalogRepository,
)


@pytest.fixture
def corporate_repo() -> AutoProvisioningCorporateRepository:
    return AutoProvisioningCorporateRepository()


@pytest.fixture
def catalog_repo() -> InMemoryMedicationHistoryCategoryCatalogRepository:
    return InMemoryMedicationHistoryCategoryCatalogRepository()


async def test_get_catalog_returns_default_when_not_found(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """TC-APP-01: 未登録法人の取得でデフォルトカタログが生成・保存されて返されること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    use_case = GetCategoryCatalogUseCase(catalog_repo, corp_access)

    corp_id = str(CorporateId.generate().value)
    result = await use_case.execute(corp_id)

    assert result.corporate_id == corp_id
    major_codes = [m.code for m in result.major_categories]
    assert "soap" in major_codes
    assert "statutory" in major_codes

    # リポジトリにも保存されていること
    saved = await catalog_repo.get(corporate_id=CorporateId.parse(corp_id))
    assert saved is not None
    assert saved.corporate_id.value == CorporateId.parse(corp_id).value


async def test_get_catalog_returns_saved_catalog(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """TC-APP-02: 既に保存されている法人の区分カタログがそのまま返されること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    get_use_case = GetCategoryCatalogUseCase(catalog_repo, corp_access)
    update_use_case = UpdateCategoryCatalogUseCase(catalog_repo, corp_access)

    corp_id = str(CorporateId.generate().value)
    # まず初期取得
    await get_use_case.execute(corp_id)

    # 更新でカスタム大区分を追加
    await update_use_case.execute(
        UpdateCategoryCatalogCommand(
            corporate_id=corp_id,
            major_categories=(
                MajorCategoryInput(code="soap", name="SOAP", display_order=1),
                MajorCategoryInput(code="custom", name="独自区分", display_order=2),
            ),
            medium_categories=(
                MediumCategoryInput(
                    code="c1",
                    major_category_code="custom",
                    name="独自中区分",
                    display_order=1,
                ),
            ),
        )
    )

    # 再度取得
    result = await get_use_case.execute(corp_id)
    assert any(m.code == "custom" for m in result.major_categories)
    assert any(m.code == "c1" for m in result.medium_categories)


async def test_update_catalog_saves_changes(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """TC-APP-03: 中区分の必須設定や追加が更新保存されること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    use_case = UpdateCategoryCatalogUseCase(catalog_repo, corp_access)

    corp_id = str(CorporateId.generate().value)
    result = await use_case.execute(
        UpdateCategoryCatalogCommand(
            corporate_id=corp_id,
            major_categories=(
                MajorCategoryInput(code="soap", name="SOAP", display_order=1),
            ),
            medium_categories=(
                MediumCategoryInput(
                    code="s",
                    major_category_code="soap",
                    name="S（必須化）",
                    display_order=1,
                    is_required=True,
                ),
            ),
        )
    )

    assert result.medium_categories[0].is_required is True
    assert result.medium_categories[0].name == "S（必須化）"


async def test_inactive_corporate_access_rejected(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """TC-APP-04: 休止中法人のカタログ操作が拒否されること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    get_use_case = GetCategoryCatalogUseCase(catalog_repo, corp_access)

    corp_id = CorporateId.generate()
    corporate_repo.set_inactive(corp_id)

    with pytest.raises(CorporateInactiveError):
        await get_use_case.execute(str(corp_id.value))


async def test_catalog_tenant_isolation(
    catalog_repo: InMemoryMedicationHistoryCategoryCatalogRepository,
    corporate_repo: AutoProvisioningCorporateRepository,
) -> None:
    """TC-TNT-01: 法人Aと法人Bのカタログが相互に隔離されていること。"""
    corp_access = create_vendor_corporate_access_for(corporate_repo)
    get_use_case = GetCategoryCatalogUseCase(catalog_repo, corp_access)
    update_use_case = UpdateCategoryCatalogUseCase(catalog_repo, corp_access)

    corp_a = str(CorporateId.generate().value)
    corp_b = str(CorporateId.generate().value)

    # 法人Aにカスタム区分を設定
    await update_use_case.execute(
        UpdateCategoryCatalogCommand(
            corporate_id=corp_a,
            major_categories=(
                MajorCategoryInput(code="corp_a_only", name="A専用", display_order=1),
            ),
            medium_categories=(
                MediumCategoryInput(
                    code="med_a",
                    major_category_code="corp_a_only",
                    name="A中区分",
                    display_order=1,
                ),
            ),
        )
    )

    # 法人Bを取得 -> デフォルトが返り、法人Aのカスタム区分は含まれない
    res_b = await get_use_case.execute(corp_b)
    assert not any(m.code == "corp_a_only" for m in res_b.major_categories)
    assert not any(m.code == "med_a" for m in res_b.medium_categories)
