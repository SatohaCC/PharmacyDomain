"""エンティティ識別子の生成・復元・検証の共通基盤。"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Self

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.base import DomainPrimitive


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
