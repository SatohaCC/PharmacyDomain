"""医薬品マスタ集約のテスト。

主眼は2つ。

1. **時点で答えが変わること**（収載日・経過措置期限）。「今」で引く実装は
   過去の処方を誤判定する。
2. リフィル適用除外の貼付剤の定義を、除外条件まで含めて正しく組み立てること。
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest

from app.base.domain.medicine import MedicineCodeType, MedicineIdentifier
from app.domain.medicine_catalog import (
    Medicine,
    MedicineCodeRequiredError,
    MedicineDosageForm,
    MedicineEffectivePeriodInvertedError,
    MedicineListedOn,
    MedicineWithdrawnOn,
    NarcoticCategory,
)
from app.domain.medicine_catalog.medicine import MedicineEffectivePeriod
from tests.factories.medicine_catalog_factory import (
    LISTED_ON,
    create_medicine,
    create_refill_restricted_patch,
)


class Test収載期間:
    """終了日を含む閉区間。経過措置期限当日までは使える。"""

    def test_収載日当日から_有効になる(self) -> None:
        """収載日は含む。前日は含まない。"""
        # Arrange
        medicine = create_medicine()

        # Act / Assert
        assert medicine.is_effective_on(LISTED_ON)
        assert not medicine.is_effective_on(LISTED_ON - timedelta(days=1))

    def test_経過措置期限の翌日から_無効になる(self) -> None:
        """期限当日を除外する実装だと、正当な調剤を弾く。"""
        # Arrange
        medicine = create_medicine(withdrawn_on=date(2026, 3, 31))

        # Act / Assert
        assert medicine.is_effective_on(date(2026, 3, 31))
        assert not medicine.is_effective_on(date(2026, 4, 1))

    def test_経過措置期限が無ければ_未来まで有効(self) -> None:
        # Arrange
        medicine = create_medicine()

        # Act / Assert
        assert medicine.is_effective_on(date(2099, 12, 31))

    def test_経過措置期限が収載日より前だと_構築できない(self) -> None:
        # Arrange / Act / Assert
        with pytest.raises(MedicineEffectivePeriodInvertedError):
            MedicineEffectivePeriod(
                listed_on=MedicineListedOn(date(2026, 4, 1)),
                withdrawn_on=MedicineWithdrawnOn(date(2026, 3, 31)),
            )

    @pytest.mark.parametrize(
        ("first", "second", "expected"),
        [
            ((date(2020, 4, 1), date(2026, 3, 31)), (date(2026, 4, 1), None), False),
            ((date(2020, 4, 1), date(2026, 3, 31)), (date(2026, 3, 31), None), True),
            ((date(2020, 4, 1), None), (date(2026, 4, 1), None), True),
        ],
    )
    def test_期間の重なりを判定できる(
        self,
        first: tuple[date, date | None],
        second: tuple[date, date | None],
        expected: bool,
    ) -> None:
        """改定で行が入れ替わるとき、期間は隣接しても重ならない。"""

        # Arrange
        def period(value: tuple[date, date | None]) -> MedicineEffectivePeriod:
            listed_on, withdrawn_on = value
            return MedicineEffectivePeriod(
                listed_on=MedicineListedOn(listed_on),
                withdrawn_on=(
                    MedicineWithdrawnOn(withdrawn_on)
                    if withdrawn_on is not None
                    else None
                ),
            )

        # Act / Assert
        assert period(first).overlaps(period(second)) is expected


class Test薬品コード:
    """マスタは薬品コードで引くためにある。"""

    def test_コードなしの行は_登録できない(self) -> None:
        """引けない行が積み上がるのを防ぐ。"""
        # Arrange
        base = create_medicine()

        # Act / Assert
        with pytest.raises(MedicineCodeRequiredError):
            dataclasses.replace(
                base,
                identifier=MedicineIdentifier(code_type=MedicineCodeType.NONE),
            )


class Test麻薬区分:
    """麻薬と向精神薬を1つの真偽値に潰さない。"""

    def test_麻薬は_麻薬処方箋の対象になる(self) -> None:
        # Arrange
        medicine = create_medicine(narcotic_category=NarcoticCategory.NARCOTIC)

        # Act / Assert
        assert medicine.is_narcotic

    def test_向精神薬は_麻薬処方箋の対象にならない(self) -> None:
        """麻薬処方箋の必須3項目は麻薬にだけ課され、向精神薬には課されない。"""
        # Arrange
        medicine = create_medicine(narcotic_category=NarcoticCategory.PSYCHOTROPIC)

        # Act / Assert
        assert not medicine.is_narcotic

    def test_全ての区分に_日本語ラベルがある(self) -> None:
        # Arrange / Act / Assert
        for category in NarcoticCategory:
            assert category.label


class Testリフィル適用除外:
    """「貼付剤（鎮痛・消炎……麻薬・向精神薬、皮膚疾患用を除く）」の組み立て。"""

    def test_鎮痛消炎の貼付剤は_リフィル不可(self) -> None:
        # Arrange
        medicine = create_refill_restricted_patch()

        # Act / Assert
        assert medicine.is_refill_restricted_patch
        assert medicine.forbids_refill

    def test_鎮痛消炎でない貼付剤は_該当しない(self) -> None:
        # Arrange
        medicine = create_medicine(dosage_form=MedicineDosageForm.PATCH)

        # Act / Assert
        assert not medicine.is_refill_restricted_patch

    def test_麻薬の貼付剤は_貼付剤の除外に当たらない(self) -> None:
        """括弧内の除外。麻薬の貼付剤は「投与量に限度」の側で扱われる。"""
        # Arrange
        medicine = create_refill_restricted_patch(
            narcotic_category=NarcoticCategory.NARCOTIC
        )

        # Act / Assert
        assert not medicine.is_refill_restricted_patch

    def test_向精神薬の貼付剤も_貼付剤の除外に当たらない(self) -> None:
        # Arrange
        medicine = create_refill_restricted_patch(
            narcotic_category=NarcoticCategory.PSYCHOTROPIC
        )

        # Act / Assert
        assert not medicine.is_refill_restricted_patch

    def test_皮膚疾患用の貼付剤は_該当しない(self) -> None:
        # Arrange
        medicine = create_refill_restricted_patch(is_dermatological=True)

        # Act / Assert
        assert not medicine.is_refill_restricted_patch

    def test_投与量に限度があれば_剤形によらずリフィル不可(self) -> None:
        """柱は2本ある。貼付剤の判定だけに寄せない。"""
        # Arrange
        medicine = create_medicine(has_dosage_limit=True)

        # Act / Assert
        assert not medicine.is_refill_restricted_patch
        assert medicine.forbids_refill

    def test_どちらにも当たらなければ_リフィル可(self) -> None:
        # Arrange
        medicine = create_medicine()

        # Act / Assert
        assert not medicine.forbids_refill


class Testテナント境界:
    """このコンテキストだけが法人IDを持たない。"""

    def test_医薬品マスタは_法人IDを持たない(self) -> None:
        """薬価基準は国が定めるので法人ごとに内容が違わない。

        `corporate_id` を付けて法人ごとに複製すると、改定のたびに全テナント分を
        更新する羽目になる。「自局で採用している薬か」は別集約の責務。
        """
        # Arrange / Act
        field_names = {item.name for item in dataclasses.fields(Medicine)}

        # Assert
        assert "corporate_id" not in field_names
        assert "store_id" not in field_names
