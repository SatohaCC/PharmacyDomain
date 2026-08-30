"""Shared Kernel の薬品単位公費負担区分のテスト。"""

from app.domain.shared.public_expense import PublicExpenseBurden


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
