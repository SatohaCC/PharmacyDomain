"""Shared Kernel の薬品語彙のテスト。

処方・調剤・薬歴の3コンテキストが共有する語彙なので、規格由来の値集合と
組み合わせ規則の境界はここで固定する。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.medicine import (
    ConversionFactor,
    DispensingQuantity,
    DosageAmount,
    DosageFormCategory,
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineLineNumber,
    MedicineName,
    MedicineUnit,
    PublicExpenseBurden,
    RpNumber,
)


class Test薬品コード種別:
    """規格により使用可能な値集合が異なることを固定する。"""

    @pytest.mark.parametrize(
        ("code_type", "expected"),
        [
            (MedicineCodeType.NONE, "1"),
            (MedicineCodeType.RECEIPT, "2"),
            (MedicineCodeType.MHLW, "3"),
            (MedicineCodeType.YJ, "4"),
            (MedicineCodeType.HOT, "6"),
            (MedicineCodeType.GENERIC, "7"),
        ],
    )
    def test_規格のレコードコードが_JAHISの備考欄と一致する(
        self, code_type: MedicineCodeType, expected: str
    ) -> None:
        # Arrange / Act / Assert: 5・8 は欠番であり 6 は HOT である
        assert code_type.record_code == expected

    @pytest.mark.parametrize(
        "code_type",
        [MedicineCodeType.RECEIPT, MedicineCodeType.YJ, MedicineCodeType.GENERIC],
    )
    def test_電子処方箋で使える種別は_処方編別表15の3つだけ(
        self, code_type: MedicineCodeType
    ) -> None:
        # Arrange / Act / Assert
        assert code_type.allowed_in_electronic_prescription

    @pytest.mark.parametrize(
        "code_type",
        [MedicineCodeType.NONE, MedicineCodeType.MHLW, MedicineCodeType.HOT],
    )
    def test_紙でのみ使える種別は_電子処方箋では使えない(
        self, code_type: MedicineCodeType
    ) -> None:
        """別表15 で 1 は「未使用」、3 と 6 は「使用しない」と定められている。"""
        # Arrange / Act / Assert
        assert not code_type.allowed_in_electronic_prescription

    def test_全種別に_日本語ラベルが定義されている(self) -> None:
        # Arrange / Act / Assert
        assert all(code_type.label for code_type in MedicineCodeType)


class Test薬品識別子:
    """コード種別とコードの有無が不可分であることを固定する。"""

    def test_コードなし種別で_コードを省略すると_生成できる(self) -> None:
        # Arrange / Act
        actual = MedicineIdentifier(code_type=MedicineCodeType.NONE)

        # Assert
        assert actual.code is None

    def test_コードなし種別に_コードを付けると_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="コードなし"):
            MedicineIdentifier(
                code_type=MedicineCodeType.NONE,
                code=MedicineCode("620000001"),
            )

    @pytest.mark.parametrize(
        "code_type",
        [
            MedicineCodeType.RECEIPT,
            MedicineCodeType.MHLW,
            MedicineCodeType.YJ,
            MedicineCodeType.HOT,
            MedicineCodeType.GENERIC,
        ],
    )
    def test_コードあり種別で_コードを省略すると_拒否される(
        self, code_type: MedicineCodeType
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="薬品コードが必要"):
            MedicineIdentifier(code_type=code_type)

    def test_YJコードは_桁数を検証しない(self) -> None:
        """原典で桁数を確認できていないため、推測で弾かない。"""
        # Arrange / Act
        actual = MedicineIdentifier(
            code_type=MedicineCodeType.YJ,
            code=MedicineCode("2171022F1029"),
        )

        # Assert
        assert actual.code == MedicineCode("2171022F1029")


class Test剤形区分:
    """処方編 別表13 / JAHIS レコードNo.101 の値集合。"""

    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            (DosageFormCategory.INTERNAL, "1"),
            (DosageFormCategory.PRN, "2"),
            (DosageFormCategory.TOPICAL, "3"),
            (DosageFormCategory.INTERNAL_DROPS, "4"),
            (DosageFormCategory.INJECTION, "5"),
            (DosageFormCategory.SUPPLY, "6"),
            (DosageFormCategory.OTHER, "9"),
        ],
    )
    def test_レコードコードが_別表13と一致する(
        self, category: DosageFormCategory, expected: str
    ) -> None:
        # Arrange / Act / Assert: 7・8 は欠番で不明は 9
        assert category.record_code == expected

    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            (DosageFormCategory.INTERNAL, "投与日数"),
            (DosageFormCategory.PRN, "投与回数"),
            (DosageFormCategory.TOPICAL, "投与日数または回数"),
        ],
    )
    def test_調剤数量の意味が_剤形区分で決まる(
        self, category: DosageFormCategory, expected: str
    ) -> None:
        # Arrange / Act / Assert
        assert category.quantity_meaning == expected


class Test分量:
    """用量は Decimal であり float を受け付けない。"""

    def test_文字列から_分量を生成できる(self) -> None:
        # Arrange / Act
        actual = DosageAmount.parse("1.5")

        # Assert
        assert actual.value == Decimal("1.5")

    def test_floatを渡すと_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="float"):
            DosageAmount(0.1)  # type: ignore[arg-type]

    def test_小数部6桁は_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="小数部"):
            DosageAmount.parse("1.000001")

    def test_0は_正の値として拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="分量"):
            DosageAmount.parse("0")

    def test_単位変換係数も_Decimalで扱う(self) -> None:
        """エンシュア・リキッド 1缶250mL を 10mL 単位へ換算する係数。"""
        # Arrange / Act
        factor = ConversionFactor.parse("250")

        # Assert
        assert DosageAmount.parse("3").value * factor.value == Decimal("750")


class Test数量プリミティブ:
    """規格のフィールド桁数（3桁）を上限として持つ。"""

    @pytest.mark.parametrize(
        "primitive", [DispensingQuantity, RpNumber, MedicineLineNumber]
    )
    def test_999までは_受け入れる(
        self, primitive: type[DispensingQuantity | RpNumber | MedicineLineNumber]
    ) -> None:
        # Arrange / Act
        actual = primitive(999)

        # Assert
        assert actual.value == 999

    @pytest.mark.parametrize(
        "primitive", [DispensingQuantity, RpNumber, MedicineLineNumber]
    )
    def test_1000以上は_拒否される(
        self, primitive: type[DispensingQuantity | RpNumber | MedicineLineNumber]
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="999"):
            primitive(1000)

    @pytest.mark.parametrize(
        "primitive", [DispensingQuantity, RpNumber, MedicineLineNumber]
    )
    def test_0は_拒否される(
        self, primitive: type[DispensingQuantity | RpNumber | MedicineLineNumber]
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="正の値"):
            primitive(0)


class Test名称プリミティブ:
    def test_薬品名称の連続空白は_1つに正規化される(self) -> None:
        # Arrange / Act
        actual = MedicineName("ノルバスク錠　　２．５ｍｇ")

        # Assert
        assert actual.value == "ノルバスク錠 ２．５ｍｇ"

    def test_薬品名称の上限は_180文字(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="180文字"):
            MedicineName("あ" * 181)

    def test_単位名の上限は_20文字(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="20文字"):
            MedicineUnit("あ" * 21)

    def test_空の薬品名称は_拒否される(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(DomainValidationError, match="空"):
            MedicineName("   ")


class Test公費負担区分:
    """JAHIS レコードNo.231。第一/第二/第三/特殊の4枠。"""

    def test_初期値は_すべて負担しない(self) -> None:
        # Arrange / Act
        actual = PublicExpenseBurden()

        # Assert
        assert not actual.bears_any

    def test_いずれかが負担するとき_bears_anyが真になる(self) -> None:
        # Arrange / Act
        actual = PublicExpenseBurden(second=True)

        # Assert
        assert actual.bears_any

    def test_特殊公費だけでも_bears_anyが真になる(self) -> None:
        """特殊公費は Claim へ写さないが、処方箋上は独立した枠として存在する。"""
        # Arrange / Act
        actual = PublicExpenseBurden(special=True)

        # Assert
        assert actual.bears_any
        assert not actual.first
