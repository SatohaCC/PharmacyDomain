"""3つ以上のコンテキストから参照される、横断的なドメインプリミティブ。"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, ClassVar, Self

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.base import DomainPrimitive


class EntityUUID(DomainPrimitive[uuid.UUID]):
    """エンティティの一意識別子（UUIDv7）を表す基底クラス。

    UUIDv7 を要求するのは、時刻順に並ぶIDにより「作成順」がIDだけで決まり、
    採番のために永続化層へ問い合わせずに済むため。採番は :meth:`generate`、
    文字列からの復元は :meth:`parse` を使い、``uuid.UUID`` を直に組み立てる
    箇所を1つに閉じ込める。
    """

    identifier_name: ClassVar[str] = "識別子"

    def validate(self) -> None:
        # 文字列などが渡されたときの AttributeError を防ぐ。
        if not isinstance(self.value, uuid.UUID):
            got = type(self.value).__name__
            raise DomainValidationError(
                f"{self.identifier_name}はUUIDインスタンスである必要があります。受け取った型: {got}。"
            )

        if self.value.version != 7:
            raise DomainValidationError(
                f"{self.identifier_name}はUUID v7である必要があります。"
            )

    @classmethod
    def generate(cls) -> Self:
        """新しい識別子を採番する。"""
        return cls(uuid.uuid7())

    @classmethod
    def parse(cls, raw: str | uuid.UUID) -> Self:
        """文字列表現（DBの列値・APIのパスパラメータ）から識別子を復元する。

        Raises:
            DomainValidationError: UUIDv7として解釈できない場合。呼び出し元が
                HTTPの4xxへ変換できるよう ``ValueError`` ではなくドメイン例外
                に統一している。
        """
        if isinstance(raw, uuid.UUID):
            return cls(raw)
        try:
            return cls(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError) as exc:
            raise DomainValidationError(
                f"{cls.identifier_name}はUUID形式の文字列である必要があります。受け取った値: {raw!r}。"
            ) from exc


class EntityStringId(DomainPrimitive[str]):
    """文字列をそのまま識別子に使うエンティティ用の基底クラス。

    :class:`EntityUUID` は集約ルート（法人・店舗・利用者・患者）に限る。内側
    の行（併用薬・アレルギー・副作用歴など）はレセコン由来の番号や取込元の
    キーをそのまま識別子にするため、UUIDを強制すると元の値を捨てるか対応表を
    持つかの二択になる。よってここでは「空でない文字列」だけを要求する。
    """

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, DomainPrimitive):
            value = value.value
        if isinstance(value, str):
            return value.strip()
        return value

    def validate(self) -> None:
        if not isinstance(self.value, str):
            got = type(self.value).__name__
            raise DomainValidationError(
                f"識別子は文字列である必要があります。受け取った型: {got}。"
            )

        if not self.value:
            raise DomainValidationError("識別子は空にできません。")

    @classmethod
    def parse(cls, raw: str) -> Self:
        """文字列から識別子を復元する。"""
        return cls(raw)


class BaseNormalizedString(DomainPrimitive[str]):
    """連続する空白の集約および前後の余白除去を行う文字列ドメインプリミティブの基底クラス。"""

    def _normalize(self, value: str) -> str:
        if not isinstance(value, str):
            raise DomainValidationError("値は文字列である必要があります。")
        return re.sub(r"\s+", " ", value).strip()

    def validate(self) -> None:
        """派生クラスで必要に応じてオーバーライドするバリデーションフック。"""
        if not self.value:
            raise DomainValidationError("値は空にできません。")


class BasePostalCode(BaseNormalizedString):
    """日本の郵便番号。7桁の半角数字をハイフン付きに正規化する。"""

    def _normalize(self, value: str) -> str:
        normalized = super()._normalize(value)
        if re.fullmatch(r"[0-9]{7}", normalized):
            return f"{normalized[:3]}-{normalized[3:]}"
        return normalized

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("郵便番号は空にできません。")
        if not re.fullmatch(r"[0-9]{3}-[0-9]{4}", self.value):
            raise DomainValidationError(
                "郵便番号は半角数字7桁（ハイフン可）で入力してください。"
            )


class BaseAddress(BaseNormalizedString):
    """住所本文（都道府県・市区町村・番地など）。"""

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("住所は空にできません。")
        if len(self.value) > 200:
            raise DomainValidationError("住所は200文字以内で指定してください。")


class BaseFreeText(DomainPrimitive[str]):
    r"""SOAP記載や服薬指導メモなど、改行を含む自由記述テキストの基底クラス。

    前後の余白除去（strip）および行末の不要な空白の削除（rstrip）を行いつつ、
    本文内の改行や複数行の構成を保持する。改行コードは '\n' に統一される。
    """

    def _normalize(self, value: str) -> str:
        if not isinstance(value, str):
            raise DomainValidationError("本文は文字列である必要があります。")

        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in normalized.split("\n")]
        return "\n".join(lines).strip()

    def validate(self) -> None:
        """派生クラスで必要に応じてオーバーライドするバリデーションフック。"""


class BaseDate(DomainPrimitive[date]):
    """日付の型チェックを持つ基底クラス。"""

    def validate(self) -> None:
        """日付型（date）であることを検証する。"""
        self._ensure_date_type()

    def _ensure_date_type(self) -> None:
        """日付型（date）であることを検証する（datetime 誤混入を防ぐ）。"""
        if not isinstance(self.value, date) or isinstance(self.value, datetime):
            got = type(self.value).__name__
            raise DomainValidationError(
                f"日付は日付型である必要があります。受け取った型: {got}。"
            )


class BaseTelephoneNumber(DomainPrimitive[str]):
    """TELとFAXに共通するバリデーションを持つ基底クラス。継承して使う。"""

    field_name: ClassVar[str] = ""

    def _normalize(self, value: str) -> str:
        if isinstance(value, str):
            normalized = value.translate(
                str.maketrans("０１２３４５６７８９", "0123456789")
            )
            return re.sub(r"[\-\sー−]", "", normalized)
        return value

    def validate(self) -> None:
        if not isinstance(self.value, str):
            got = type(self.value).__name__
            raise DomainValidationError(
                f"{self.field_name}は文字列である必要があります。受け取った型: {got}。"
            )

        # FAXなど未設定を許容する用途があるため、空値は検証せず通す。
        if not self.value:
            return

        if not re.match(r"^0\d{9,10}$", self.value):
            # 派生クラスの field_name を埋め込み、TEL/FAX どちらのエラーかを区別する。
            raise DomainValidationError(
                f"{self.field_name}は0で始まる10桁または11桁の数字である必要があります。"
            )


class BaseEmailAddress(BaseNormalizedString):
    """メールアドレスの基底クラス（小文字化の正規化とフォーマット検証）。"""

    def _normalize(self, value: str) -> str:
        if not isinstance(value, str):
            raise DomainValidationError("メールアドレスは文字列である必要があります。")
        return super()._normalize(value).lower()

    def validate(self) -> None:
        if not self.value:
            raise DomainValidationError("メールアドレスは空にできません。")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", self.value):
            raise DomainValidationError("メールアドレスの形式が不正です。")


class BaseNonNegativeInt(DomainPrimitive[int]):
    """0以上の整数を表す基底クラス。"""

    def validate(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise DomainValidationError("値は整数である必要があります。")
        if self.value < 0:
            raise DomainValidationError("値は0以上である必要があります。")


class BasePositiveInt(BaseNonNegativeInt):
    """1以上の正の整数を表す基底クラス。"""

    def validate(self) -> None:
        super().validate()
        if self.value <= 0:
            raise DomainValidationError("値は正の値である必要があります。")


class BaseNonNegativeFloat(DomainPrimitive[float]):
    """0以上の実数を表す基底クラス（点数・用量・価格用）。"""

    def validate(self) -> None:
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise DomainValidationError("値は数値である必要があります。")
        if self.value < 0:
            raise DomainValidationError("値は0以上である必要があります。")


class BasePositiveFloat(BaseNonNegativeFloat):
    """0より大きい正の実数を表す基底クラス。"""

    def validate(self) -> None:
        super().validate()
        if self.value <= 0:
            raise DomainValidationError("値は正の値である必要があります。")
