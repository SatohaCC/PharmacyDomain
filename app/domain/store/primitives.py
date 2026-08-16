import re
from dataclasses import dataclass
from typing import Self

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import (
    BaseAddress,
    BaseEmailAddress,
    BaseNormalizedString,
    BasePostalCode,
    BaseTelephoneNumber,
    EntityUUID,
)


class StoreId(EntityUUID):
    """店舗識別子（UUIDv7）"""

    identifier_name = "店舗ID"


class StorePostalCode(BasePostalCode):
    """店舗所在地の郵便番号"""


class StoreAddressLine(BaseAddress):
    """店舗所在地の住所本文（都道府県・市区町村・番地など）"""


class StorePhoneNumber(BaseTelephoneNumber):
    """店舗の代表電話番号"""

    field_name = "電話番号"


class StoreFaxNumber(BaseTelephoneNumber):
    """店舗のFAX番号（未発行を許容する）"""

    field_name = "FAX番号"


class StoreEmailAddress(BaseEmailAddress):
    """店舗の連絡先メールアドレス"""


class StoreName(BaseNormalizedString):
    """店舗名（正式名称）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("店舗名は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError("店舗名は100文字以内で指定してください。")


class StoreNameKana(BaseNormalizedString):
    """店舗名（フリガナ）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("店舗名（カナ）は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError(
                "店舗名（カナ）は100文字以内で指定してください。"
            )

        # 全角カタカナ・スペース以外の文字が入っていないかチェック。
        # 開始を「ァ」(U+30A1) にするのは、「ファーマシー」のように小書きの「ァ」で
        # 始まる拗音が薬局名に頻出するため。「ア」(U+30A2) 始まりだと弾いてしまう。
        # 終端の「ヶ」(U+30F6) までで「ヴ」「ヵ」を含む。長音符と中黒は範囲外のため個別に許可する。
        if not re.fullmatch(r"[ァ-ヶー・\s]+", self.value):
            raise DomainValidationError(
                "店舗名（カナ）は全角カタカナで入力してください。"
            )


class StoreNameRomaji(BaseNormalizedString):
    """店舗名（ローマ字）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("店舗名（ローマ字）は空にできません。")
        if len(self.value) > 100:
            raise DomainValidationError(
                "店舗名（ローマ字）は100文字以内で指定してください。"
            )

        # 半角英数字・記号以外の文字が入っていないかチェック。
        if not re.fullmatch(r"[a-zA-Z0-9\s\-_.,'&]+", self.value):
            raise DomainValidationError(
                "店舗名（ローマ字）は半角英数字・記号で入力してください。"
            )


class StoreCode(BaseNormalizedString):
    """店舗コード（例: ST-001 などの識別コード）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("店舗コードは空にできません。")
        if len(self.value) > 20:
            raise DomainValidationError("店舗コードは20文字以内で指定してください。")


@dataclass(frozen=True, kw_only=True)
class StoreNames:
    """店舗名の一式（正式名称・フリガナ・ローマ字）"""

    name: StoreName
    kana: StoreNameKana
    romaji: StoreNameRomaji | None = None

    def __post_init__(self) -> None:
        """店舗名を構成する値オブジェクトの型整合性を検証する。"""
        if not isinstance(self.name, StoreName):
            raise DomainValidationError("正式名称は StoreName で指定してください。")
        if not isinstance(self.kana, StoreNameKana):
            raise DomainValidationError("フリガナは StoreNameKana で指定してください。")
        if self.romaji is not None and not isinstance(self.romaji, StoreNameRomaji):
            raise DomainValidationError(
                "ローマ字は StoreNameRomaji で指定してください。"
            )


@dataclass(frozen=True, kw_only=True)
class StoreAddress:
    """所在地情報（郵便番号と住所）。"""

    postal_code: StorePostalCode
    address: StoreAddressLine  # 例: "〇〇1-2-3"

    def __post_init__(self) -> None:
        """住所を構成する値オブジェクトの型整合性を検証する。"""
        if not isinstance(self.postal_code, StorePostalCode):
            raise DomainValidationError(
                "郵便番号は StorePostalCode で指定してください。"
            )
        if not isinstance(self.address, StoreAddressLine):
            raise DomainValidationError("住所は StoreAddressLine で指定してください。")


@dataclass(frozen=True, kw_only=True)
class ContactInfo:
    """連絡先情報。"""

    phone_number: StorePhoneNumber
    fax_number: StoreFaxNumber | None = None
    email: StoreEmailAddress | None = None

    @classmethod
    def create(
        cls,
        *,
        phone_number: StorePhoneNumber,
        fax_number: StoreFaxNumber | None = None,
        email: StoreEmailAddress | None = None,
    ) -> Self:
        """空の任意連絡先を ``None`` に正規化して生成する。"""
        return cls(
            phone_number=phone_number,
            fax_number=fax_number if fax_number and fax_number.value else None,
            email=email if email and email.value else None,
        )

    def __post_init__(self) -> None:
        """必須の電話番号と任意項目の型を検証する。"""
        # TEL と FAX は別型なので、取り違えはここで落ちる。
        if not isinstance(self.phone_number, StorePhoneNumber):
            raise DomainValidationError(
                "電話番号は StorePhoneNumber で指定してください。"
            )
        if not self.phone_number.value:
            raise DomainValidationError("電話番号は空にできません。")

        if self.fax_number is not None and not isinstance(
            self.fax_number, StoreFaxNumber
        ):
            raise DomainValidationError("FAX番号は StoreFaxNumber で指定してください。")
        if self.email is not None and not isinstance(self.email, StoreEmailAddress):
            raise DomainValidationError(
                "メールアドレスは StoreEmailAddress で指定してください。"
            )


class InsurancePharmacyNumber(BaseNormalizedString):
    """保険薬局指定番号 / 医療機関コード（10桁）"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("保険薬局指定番号は空にできません。")

        # 1. 10桁の半角数字チェック
        if not re.fullmatch(r"[0-9]{10}", self.value):
            raise DomainValidationError(
                "保険薬局指定番号は半角数字10桁で入力してください。"
            )

        # 2. 上2桁が都道府県コード（01〜47）であるかを確認する。
        prefecture_code = int(self.value[:2])
        if not 1 <= prefecture_code <= 47:
            raise DomainValidationError(
                "保険薬局指定番号の都道府県コード（上2桁）が不正です。"
            )

        # 3. 3桁目が調剤区分（'4'）であるかのドメインルールチェック
        if self.value[2] != "4":
            raise DomainValidationError(
                "保険薬局指定番号の3桁目（調剤区分）は '4' である必要があります。"
            )
