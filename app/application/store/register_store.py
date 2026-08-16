"""店舗登録ユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import (
    CorporateAccessBoundary,
    Permission,
)
from app.application.store.support import to_optional_text
from app.domain.corporate.primitives import CorporateId
from app.domain.store.primitives import (
    ContactInfo,
    InsurancePharmacyNumber,
    StoreAddress,
    StoreAddressLine,
    StoreCode,
    StoreEmailAddress,
    StoreFaxNumber,
    StoreId,
    StoreName,
    StoreNameKana,
    StoreNameRomaji,
    StoreNames,
    StorePhoneNumber,
    StorePostalCode,
)
from app.domain.store.repository import StoreRepository
from app.domain.store.services import (
    InsurancePharmacyNumberUniquenessService,
    StoreCodeUniquenessService,
    StoreNameUniquenessService,
)
from app.domain.store.store import Store


@dataclass(frozen=True, kw_only=True)
class RegisterStoreCommand:
    """店舗登録に必要な入力データ（DTO）。"""

    #: 所属先となる法人のID。認証済みのテナントIDを詰めること（後述の Note を参照）。
    corporate_id: str
    name: str
    name_kana: str
    postal_code: str
    address: str
    phone_number: str
    name_romaji: str | None = None
    fax_number: str | None = None
    email: str | None = None
    code: str | None = None
    insurance_pharmacy_number: str | None = None


class RegisterStoreUseCase:
    """店舗を新規登録するアプリケーションサービス。"""

    def __init__(
        self,
        repository: StoreRepository,
        name_uniqueness_service: StoreNameUniquenessService,
        code_uniqueness_service: StoreCodeUniquenessService,
        insurance_number_uniqueness_service: InsurancePharmacyNumberUniquenessService,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._name_uniqueness_service = name_uniqueness_service
        self._code_uniqueness_service = code_uniqueness_service
        self._insurance_number_uniqueness_service = insurance_number_uniqueness_service
        self._corporate_access = corporate_access

    async def execute(self, command: RegisterStoreCommand) -> StoreId:
        """店舗を登録し、採番された店舗IDを返す。

        Note:
            ``corporate_id`` は操作対象の法人IDであり、認証済みActorの権限と
            ``CorporateAccessService`` によって、対象法人の存在・有効状態・操作権限を
            先に確認する。店舗集約が法人集約を直接参照することはない。

        Raises:
            DomainValidationError: 入力値がドメインの制約を満たさない場合。
            StoreNameAlreadyExistsError: 同一法人内に同名の店舗が既に存在する場合。
            StoreCodeAlreadyExistsError: 同一法人内に同一コードの店舗が既に存在する場合。
            InsurancePharmacyNumberAlreadyExistsError: 保険薬局指定番号が別の店舗で
                既に使用されている場合。
        """
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_STORE,
        )

        # 任意項目は空文字・空白のみを「未設定」に揃えてから値オブジェクトへ変換する。
        raw_romaji = to_optional_text(command.name_romaji)
        raw_fax_number = to_optional_text(command.fax_number)
        raw_email = to_optional_text(command.email)
        raw_code = to_optional_text(command.code)
        raw_insurance_number = to_optional_text(command.insurance_pharmacy_number)

        names = StoreNames(
            name=StoreName(command.name),
            kana=StoreNameKana(command.name_kana),
            romaji=StoreNameRomaji(raw_romaji) if raw_romaji else None,
        )
        address = StoreAddress(
            postal_code=StorePostalCode(command.postal_code),
            address=StoreAddressLine(command.address),
        )
        contact_info = ContactInfo.create(
            phone_number=StorePhoneNumber(command.phone_number),
            fax_number=(StoreFaxNumber(raw_fax_number) if raw_fax_number else None),
            email=StoreEmailAddress(raw_email) if raw_email else None,
        )
        code = StoreCode(raw_code) if raw_code else None
        insurance_pharmacy_number = (
            InsurancePharmacyNumber(raw_insurance_number)
            if raw_insurance_number
            else None
        )

        await self._name_uniqueness_service.ensure_name_is_unique(
            corporate_id=corporate_id,
            name=names.name,
        )
        if code is not None:
            await self._code_uniqueness_service.ensure_code_is_unique(
                corporate_id=corporate_id,
                code=code,
            )
        if insurance_pharmacy_number is not None:
            await self._insurance_number_uniqueness_service.ensure_number_is_unique(
                number=insurance_pharmacy_number,
            )

        store = Store.create(
            corporate_id=corporate_id,
            names=names,
            address=address,
            contact_info=contact_info,
            code=code,
            insurance_pharmacy_number=insurance_pharmacy_number,
        )
        await self._repository.save(store)
        return store.id
