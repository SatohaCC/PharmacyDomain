from app.domain.corporate.primitives import CorporateId
from app.domain.store.exceptions import (
    InsurancePharmacyNumberAlreadyExistsError,
    StoreCodeAlreadyExistsError,
    StoreNameAlreadyExistsError,
)
from app.domain.store.primitives import (
    InsurancePharmacyNumber,
    StoreCode,
    StoreId,
    StoreName,
)
from app.domain.store.repository import StoreRepository


class StoreNameUniquenessService:
    """同一法人内の店舗名の重複を防ぐドメインサービス。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def ensure_name_is_unique(
        self,
        *,
        corporate_id: CorporateId,
        name: StoreName,
        excluding_id: StoreId | None = None,
    ) -> None:
        """同一法人内で店舗名が重複していないことを検証する。

        Args:
            corporate_id: 所属法人のID
            name: 検証対象の店舗名
            excluding_id: 更新時に除外する店舗ID（新規登録時は None）

        Raises:
            StoreNameAlreadyExistsError: 既に同名の店舗が存在する場合
        """
        is_exists = await self._repository.exists_by_name(
            corporate_id=corporate_id,
            name=name,
            excluding_id=excluding_id,
        )
        if is_exists:
            raise StoreNameAlreadyExistsError(
                f"同一法人内に店舗名 '{name.value}' は既に登録されています。"
            )


class StoreCodeUniquenessService:
    """同一法人内の店舗コードの重複を防ぐドメインサービス。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def ensure_code_is_unique(
        self,
        *,
        corporate_id: CorporateId,
        code: StoreCode,
        excluding_id: StoreId | None = None,
    ) -> None:
        """同一法人内で店舗コードが重複していないことを検証する。"""
        is_exists = await self._repository.exists_by_code(
            corporate_id=corporate_id,
            code=code,
            excluding_id=excluding_id,
        )
        if is_exists:
            raise StoreCodeAlreadyExistsError(
                f"同一法人内に店舗コード '{code.value}' は既に登録されています。"
            )


class InsurancePharmacyNumberUniquenessService:
    """保険薬局指定番号の重複を防ぐドメインサービス。"""

    def __init__(self, repository: StoreRepository) -> None:
        self._repository = repository

    async def ensure_number_is_unique(
        self,
        *,
        number: InsurancePharmacyNumber,
        excluding_id: StoreId | None = None,
    ) -> None:
        """指定番号が別の店舗に登録されていないことを検証する。"""
        is_exists = await self._repository.exists_by_insurance_pharmacy_number(
            number=number,
            excluding_id=excluding_id,
        )
        if is_exists:
            raise InsurancePharmacyNumberAlreadyExistsError(
                f"保険薬局指定番号 '{number.value}' は既に別の店舗で登録されています。"
            )
