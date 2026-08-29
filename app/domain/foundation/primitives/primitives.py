"""3つ以上のコンテキストから参照される、横断的なドメインプリミティブ。"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
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


class BaseAwareTimestamp(DomainPrimitive[datetime]):
    """タイムゾーン付き日時の基底クラス。UTCへ正規化して保持する。

    naive な日時は「どのタイムゾーンで記録されたか」を復元できず監査に使えない
    ため拒否する。同じ検証を各コンテキストへ書き写すと、片方だけ naive を
    受け入れる実装に倒れるので、定義はここ1つに閉じる
    （``ensure_digits`` と同じ理由）。

    現在時刻の取得は行わない。値は注入された ``Clock`` 由来のものを受け取る
    （AGENTS.md「資格の時間境界」。ruff ``DTZ005`` が裸の ``datetime.now()``
    を禁止している）。
    """

    #: エラーメッセージに出す項目名。継承側で上書きする。
    timestamp_name: ClassVar[str] = "日時"

    def _normalize(self, value: datetime) -> datetime:
        if not isinstance(value, datetime):
            raise DomainValidationError(
                f"{self.timestamp_name}は日時型で指定してください。"
            )
        if value.tzinfo is None or value.utcoffset() is None:
            raise DomainValidationError(
                f"{self.timestamp_name}はタイムゾーン付きで指定してください。"
            )
        return value.astimezone(UTC)

    def validate(self) -> None:
        """日時型であることを検証する。"""
        if not isinstance(self.value, datetime):
            raise DomainValidationError(
                f"{self.timestamp_name}は日時型で指定してください。"
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


def ensure_digits(value: str, *, field_name: str, lengths: tuple[int, ...]) -> None:
    """半角数字かつ規定桁数であることを検証する。

    レセプト・処方箋で桁数が定まっている番号（保険者番号、公費負担者番号、
    公費受給者番号、枝番、医療機関コード等）は、桁数が違えば提出時に返戻される。
    登録時に弾かないと不正値がそのまま Snapshot へ凍結され、請求まで気付けない
    ため、桁数はプリミティブの不変条件として持たせる。

    同じ規則を Coverage / Claim / Prescription が必要とする。規則本体が複数箇所に
    あると片方だけ直る事故が起きるので、Domain基盤に1つだけ置く
    （``priority_rules.py`` と同じ判断）。この関数は ``str`` と ``int`` しか
    扱わず、各Domainコンテキストへ依存しない。
    """
    pattern = "|".join(f"[0-9]{{{length}}}" for length in lengths)
    if not re.fullmatch(pattern, value):
        expected = "桁または".join(str(length) for length in lengths)
        raise DomainValidationError(
            f"{field_name}は半角数字{expected}桁で指定してください。"
        )


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


class BaseNonNegativeDecimal(DomainPrimitive[Decimal]):
    """0以上の十進数を表す基底クラス（用量・変換係数・点数用）。

    ``float`` を使わない。用量には 0.05 刻みが実在し、二進浮動小数では
    ``0.05 + 0.05 + 0.05`` が ``0.15`` と一致しない。処方箋の不均等服用は
    「各回服用量の合計が1日量と一致すること」を不変条件に持つため、
    ``float`` で実装すると正当な処方を弾く（実在する用量刻み19種から
    3回分を総当りした 6,859 通りのうち 869 通り＝12.7% が不一致）。

    コンストラクタは ``Decimal`` だけを受け取り、文字列からの復元は
    :meth:`parse` に閉じ込める（``EntityUUID`` が ``uuid.UUID`` を直に
    組み立てる箇所を1つにしているのと同じ形）。Python に十進数リテラルは
    無いので、呼び出し側は ``DosageAmount(Decimal("1.5"))`` または
    ``DosageAmount.parse("1.5")`` と書く。

    ``Decimal(0.1)`` のように float 経由で作られた値は
    ``0.1000000000000000055511151231257827021181583404541015625`` になり、
    小数部55桁として :meth:`_ensure_digits_within_limit` が弾く。逆に
    ``Decimal(0.5)`` は二進で厳密に表現できるため誤差を持たず、通ってよい。
    桁数上限がそのまま「float 由来の誤差」の検出器として働く。
    """

    #: 整数部の最大桁数。派生クラスで上書きする。
    max_integer_digits: ClassVar[int] = 12
    #: 小数部の最大桁数。派生クラスで上書きする。
    max_decimal_places: ClassVar[int] = 5
    #: エラーメッセージに使う項目名。派生クラスで上書きする。
    quantity_name: ClassVar[str] = "値"

    def _normalize(self, value: Any) -> Any:
        """型注釈を無視した呼び出しに備えた実行時の防御。

        ``float`` は誤差を持ち込むため、値が入ってくる瞬間に拒否する。
        後段で丸めても失われた情報は取り戻せない。
        """
        if isinstance(value, bool):
            raise DomainValidationError(
                f"{self.quantity_name}は数値である必要があります。"
            )
        if isinstance(value, float):
            raise DomainValidationError(
                f"{self.quantity_name}は誤差が入らないよう、floatではなく"
                f"Decimalで指定してください。文字列からは parse() を使います。"
                f"受け取った値: {value!r}。"
            )
        return value

    @classmethod
    def parse(cls, raw: str | int | Decimal) -> Self:
        """外部入力（DBの列値・APIのリクエスト・CSV）から復元する。

        Raises:
            DomainValidationError: 十進数として解釈できない場合。呼び出し元が
                HTTPの4xxへ変換できるよう ``InvalidOperation`` ではなく
                ドメイン例外に統一している。
        """
        if isinstance(raw, Decimal):
            return cls(raw)
        try:
            return cls(Decimal(str(raw).strip()))
        except InvalidOperation as exc:
            raise DomainValidationError(
                f"{cls.quantity_name}は数値として解釈できる必要があります。"
                f"受け取った値: {raw!r}。"
            ) from exc

    def validate(self) -> None:
        if not isinstance(self.value, Decimal):
            got = type(self.value).__name__
            raise DomainValidationError(
                f"{self.quantity_name}は数値である必要があります。受け取った型: {got}。"
            )
        if not self.value.is_finite():
            raise DomainValidationError(
                f"{self.quantity_name}は有限の数値である必要があります。"
            )
        if self.value < 0:
            raise DomainValidationError(
                f"{self.quantity_name}は0以上である必要があります。"
            )
        self._ensure_digits_within_limit()

    def _ensure_digits_within_limit(self) -> None:
        """整数部・小数部の桁数が規定内であることを検証する。"""
        _sign, digits, exponent = self.value.as_tuple()
        if not isinstance(exponent, int):
            # NaN / Infinity のときだけ 'n' / 'N' / 'F' が入る。直前の
            # is_finite() で除外済みだが、型としては到達しうるため潰す。
            raise DomainValidationError(
                f"{self.quantity_name}は有限の数値である必要があります。"
            )
        decimal_places = max(0, -exponent)
        integer_digits = max(0, len(digits) + exponent)
        if decimal_places > self.max_decimal_places:
            raise DomainValidationError(
                f"{self.quantity_name}の小数部は{self.max_decimal_places}桁以内で"
                f"指定してください。"
            )
        if integer_digits > self.max_integer_digits:
            raise DomainValidationError(
                f"{self.quantity_name}の整数部は{self.max_integer_digits}桁以内で"
                f"指定してください。"
            )


class BasePositiveDecimal(BaseNonNegativeDecimal):
    """0より大きい十進数を表す基底クラス。"""

    def validate(self) -> None:
        super().validate()
        if self.value <= 0:
            raise DomainValidationError(
                f"{self.quantity_name}は正の値である必要があります。"
            )
