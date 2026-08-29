from dataclasses import dataclass, replace
from typing import Self

from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.entity import AggregateRoot
from app.domain.store.primitives import (
    ContactInfo,
    InsurancePharmacyNumber,
    StoreAddress,
    StoreCode,
    StoreId,
    StoreNames,
)


# 💡 修正1: frozen=True を追加
@dataclass(frozen=True, eq=False, kw_only=True)
class Store(AggregateRoot[StoreId]):
    """店舗（薬局）エンティティ（集約ルート）"""

    id: StoreId
    #: 所属法人。集約をまたぐためIDのみを持ち、法人集約そのものは参照しない。
    #: 実在性は永続化層の外部キー制約で担保する。
    corporate_id: CorporateId
    names: StoreNames
    address: StoreAddress
    contact_info: ContactInfo
    # --- 任意項目（未定・未発行を許容） ---
    code: StoreCode | None = None
    insurance_pharmacy_number: InsurancePharmacyNumber | None = None

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        names: StoreNames,
        address: StoreAddress,
        contact_info: ContactInfo,
        code: StoreCode | None = None,
        insurance_pharmacy_number: InsurancePharmacyNumber | None = None,
    ) -> Self:
        """新規店舗のファクトリメソッド"""
        return cls(
            id=StoreId.generate(),
            corporate_id=corporate_id,
            code=code,
            names=names,
            address=address,
            contact_info=contact_info,
            insurance_pharmacy_number=insurance_pharmacy_number,
        )

    # ------------------------------------------------------------------
    # ドメインメソッド（状態変更）
    #
    # イミュータブル設計のため、自身の中身は書き換えず、
    # 変更された状態を持つ「新しい Store インスタンス」を返す。
    # ------------------------------------------------------------------

    def change_names(self, new_names: StoreNames) -> Self:
        """店舗名（一式）を変更する"""
        return replace(self, names=new_names)

    def change_address(self, new_address: StoreAddress) -> Self:
        """所在地情報を変更する"""
        return replace(self, address=new_address)

    def change_contact_info(self, new_contact_info: ContactInfo) -> Self:
        """連絡先情報（電話・FAX・メール）を変更する"""
        return replace(self, contact_info=new_contact_info)

    def change_code(self, new_code: StoreCode | None) -> Self:
        """店舗コードを変更または解除する"""
        return replace(self, code=new_code)

    def change_insurance_pharmacy_number(
        self, new_number: InsurancePharmacyNumber | None
    ) -> Self:
        """保険薬局指定番号（10桁）を更新または解除する"""
        return replace(self, insurance_pharmacy_number=new_number)
