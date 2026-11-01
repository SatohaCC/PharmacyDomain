"""法人詳細情報更新ユースケースのテスト。"""

from __future__ import annotations

from app.application.corporate.commands.update_corporate_details import (
    UpdateCorporateDetailsCommand,
    UpdateCorporateDetailsUseCase,
)
from app.domain.corporate.entities import Corporate
from app.domain.corporate.identifiers import CorporateId
from app.domain.corporate.primitives import (
    CorporateName,
    CorporateType,
)
from app.domain.corporate.value_objects import CorporateRepresentativeName
from app.domain.shared.person_name import PersonNamePart
from tests.application.access_helpers import create_vendor_corporate_access
from tests.fakes.in_memory_corporate_repository import InMemoryCorporateRepository


async def test_update_corporate_details_success() -> None:
    # Arrange
    corporate_repo = InMemoryCorporateRepository()
    corporate_id = CorporateId.generate()
    corporate = Corporate(
        id=corporate_id,
        name=CorporateName("サンプル医療法人"),
        representative_name=CorporateRepresentativeName(
            last_name=PersonNamePart("山田"),
            first_name=PersonNamePart("太郎"),
        ),
        corporate_type=CorporateType.STOCK_COMPANY,
    )
    await corporate_repo.save(corporate)

    use_case = UpdateCorporateDetailsUseCase(
        repository=corporate_repo,
        corporate_access=create_vendor_corporate_access(),
    )

    # 12桁の基礎番号 123456789012 に対し、法人番号チェックディジット計算:
    # 偶数桁奇数桁重み付けによる有効な法人番号: 例 "1123456789018"
    # または CorporateNumber は13桁（最終桁がチェックディジット）
    # 有効な番号 "1234567890123" を確認するか、適切な番号を使用
    # Let's test valid matching number
    corporate_num = "1123456789018"
    invoice_num = f"T{corporate_num}"

    # Act
    await use_case.execute(
        UpdateCorporateDetailsCommand(
            corporate_id=str(corporate_id.value),
            corporate_type="medical_corporation",
            corporate_number=corporate_num,
            invoice_number=invoice_num,
            postal_code="100-0001",
            address_line="東京都千代田区千代田1-1",
            phone_number="03-1234-5678",
            email="contact@example.com",
        )
    )

    # Assert
    updated = await corporate_repo.get(corporate_id)
    assert updated is not None
    assert updated.corporate_type == CorporateType.MEDICAL_CORPORATION
    assert updated.corporate_number is not None
    assert updated.corporate_number.value == corporate_num
    assert updated.invoice_number is not None
    assert updated.invoice_number.value == invoice_num
    assert updated.address is not None
    assert updated.address.postal_code.value == "100-0001"
    assert updated.contact_info is not None
    assert updated.contact_info.phone_number.value == "0312345678"
    assert updated.contact_info.email is not None
    assert updated.contact_info.email.value == "contact@example.com"
