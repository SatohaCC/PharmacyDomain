"""医薬品マスタを配線した状態での処方箋登録のテスト。

**このファイルが、医薬品マスタを作った理由そのものである。**

マスタが無かった間、``MedicineRestrictionBoundary`` は「不明」しか答えられず、
麻薬処方箋とリフィル処方箋は fail-closed で**登録できなかった**。
分岐で回避せず失敗させる設計にしてあったので、
マスタを配線すれば分岐を1つも消さずに通るようになる。ここではその両方
（配線すれば通る／未収載なら依然として通らない）を固定する。
"""

from __future__ import annotations

from datetime import date

import pytest

from app.application.composition import MedicineCatalogRestrictionAdapter
from app.application.prescription import (
    PrescriptionManagementInput,
    RegisterPrescriptionCommand,
    RegisterPrescriptionUseCase,
)
from app.domain.medicine_catalog import (
    Medicine,
    MedicineCatalogRepository,
    NarcoticCategory,
)
from app.domain.prescription import (
    MedicineClassificationMissingError,
    NarcoticPrescriptionDetailsRequiredError,
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
    RefillNotAllowedError,
)
from tests.application.access_helpers import create_vendor_corporate_access_for
from tests.application.prescription.helpers import (
    ISSUED_ON,
    PrescriptionFixture,
    create_fixture,
    create_medicine_input,
    create_register_command,
    create_rp_input,
)
from tests.factories.medicine_catalog_factory import (
    MEDICINE_CODE,
    create_medicine,
    create_refill_restricted_patch,
)
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)

_NARCOTIC_INPUT = PrescriptionManagementInput(
    narcotic_license_number="13-1234",
    patient_address="東京都千代田区1-2-3",
    patient_phone_number="0312345678",
)
_REFILL_INPUT = PrescriptionManagementInput(refill_count=3)


async def _catalog_with(*medicines: Medicine) -> MedicineCatalogRepository:
    """マスタへ登録済みのRepositoryを組み立てる。"""
    repository = InMemoryMedicineCatalogRepository()
    for medicine in medicines:
        await repository.save(medicine)
    return repository


def _use_case(
    fixture: PrescriptionFixture, catalog: MedicineCatalogRepository
) -> RegisterPrescriptionUseCase:
    """医薬品マスタを実アダプタ経由で配線した登録ユースケースを組み立てる。

    Fake の ``MedicineRestrictionBoundary`` を実アダプタへ差し替えるだけで、
    UseCase 側は1行も変えない。
    """
    return RegisterPrescriptionUseCase(
        fixture.repository,
        create_vendor_corporate_access_for(fixture.corporate_repository),
        fixture.store_reference,
        fixture.patient_reference,
        MedicineCatalogRestrictionAdapter(catalog),
        fixture.public_expense,
        PrescriptionDocumentNumberUniquenessService(),
        NarcoticPrescriptionService(),
        RefillEligibilityService(),
        PublicExpenseBurdenService(),
    )


def _command(
    fixture: PrescriptionFixture,
    *,
    code: str = MEDICINE_CODE,
    management_info: PrescriptionManagementInput | None = None,
) -> RegisterPrescriptionCommand:
    """指定した薬品コード1件を含む登録コマンドを組み立てる。"""
    return create_register_command(
        corporate_id=fixture.corporate_id,
        store_id=fixture.store_id,
        patient_id=fixture.patient_id,
        rps=(create_rp_input(medicines=(create_medicine_input(code=code),)),),
        management_info=management_info,
    )


class Testマスタを配線すると通るようになる:
    """fail-closed だった経路が、分岐を消さずに開通する。"""

    async def test_通常の処方箋を_マスタ経由で登録できる(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        use_case = _use_case(fixture, await _catalog_with(create_medicine()))

        # Act
        actual = await use_case.execute(_command(fixture))

        # Assert
        assert actual.rps[0].medicines[0].code == MEDICINE_CODE

    async def test_麻薬処方箋を_麻薬情報つきで登録できる(self) -> None:
        """マスタが無かった間は ``UNKNOWN`` で必ず失敗していた経路。"""
        # Arrange
        fixture = create_fixture(register_medicine=False)
        catalog = await _catalog_with(
            create_medicine(narcotic_category=NarcoticCategory.NARCOTIC)
        )
        use_case = _use_case(fixture, catalog)

        # Act
        actual = await use_case.execute(
            _command(fixture, management_info=_NARCOTIC_INPUT)
        )

        # Assert
        assert actual.management_info.narcotic_license_number == "13-1234"

    async def test_麻薬なのに麻薬情報が無ければ_依然として拒否される(self) -> None:
        """マスタを入れても麻薬処方箋の必須事項は緩まない。"""
        # Arrange
        fixture = create_fixture(register_medicine=False)
        catalog = await _catalog_with(
            create_medicine(narcotic_category=NarcoticCategory.NARCOTIC)
        )
        use_case = _use_case(fixture, catalog)

        # Act / Assert
        with pytest.raises(NarcoticPrescriptionDetailsRequiredError):
            await use_case.execute(_command(fixture))

    async def test_リフィル処方箋を_登録できる(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        use_case = _use_case(fixture, await _catalog_with(create_medicine()))

        # Act
        actual = await use_case.execute(
            _command(fixture, management_info=_REFILL_INPUT)
        )

        # Assert
        assert actual.management_info.refill_count == 3

    async def test_鎮痛消炎の貼付剤は_リフィルにできない(self) -> None:
        """マスタの4つの事実から導出した結果が、そのまま登録を弾く。"""
        # Arrange
        fixture = create_fixture(register_medicine=False)
        patch = create_refill_restricted_patch()
        use_case = _use_case(fixture, await _catalog_with(patch))
        code = patch.identifier.code
        assert code is not None

        # Act / Assert
        with pytest.raises(RefillNotAllowedError):
            await use_case.execute(
                _command(fixture, code=code.value, management_info=_REFILL_INPUT)
            )

    async def test_投与量に限度がある医薬品は_リフィルにできない(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        use_case = _use_case(
            fixture, await _catalog_with(create_medicine(has_dosage_limit=True))
        )

        # Act / Assert
        with pytest.raises(RefillNotAllowedError):
            await use_case.execute(_command(fixture, management_info=_REFILL_INPUT))


class Test未収載は依然として通らない:
    """マスタを入れてもfail-closedは保たれる。"""

    async def test_マスタに無い薬品は_登録できない(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        use_case = _use_case(fixture, await _catalog_with())

        # Act / Assert
        with pytest.raises(MedicineClassificationMissingError):
            await use_case.execute(_command(fixture))

    async def test_交付日に経過措置が切れている薬品は_登録できない(self) -> None:
        """処方箋の交付日で引くので、期限切れの薬品は「無い」のと同じになる。"""
        # Arrange
        fixture = create_fixture(register_medicine=False)
        expired = create_medicine(
            listed_on=date(2020, 4, 1), withdrawn_on=ISSUED_ON.replace(day=1)
        )
        use_case = _use_case(fixture, await _catalog_with(expired))

        # Act / Assert
        with pytest.raises(MedicineClassificationMissingError):
            await use_case.execute(_command(fixture))

    async def test_交付日に有効なら_期限が近くても登録できる(self) -> None:
        """境界。交付日 = 経過措置期限当日は通る。"""
        # Arrange
        fixture = create_fixture(register_medicine=False)
        expiring = create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=ISSUED_ON)
        use_case = _use_case(fixture, await _catalog_with(expiring))

        # Act
        actual = await use_case.execute(_command(fixture))

        # Assert
        assert actual.period.issued_date == ISSUED_ON.isoformat()


class Test適用日は処方箋の交付日:
    """登録を実行した日ではなく、その処方箋が書かれた日のマスタで判定する。"""

    async def test_交付日より後の改定は_判定に影響しない(self) -> None:
        # Arrange: 交付日の翌日から麻薬指定になる薬品
        fixture = create_fixture(register_medicine=False)
        catalog = await _catalog_with(
            create_medicine(listed_on=date(2020, 4, 1), withdrawn_on=ISSUED_ON),
            create_medicine(
                listed_on=ISSUED_ON.replace(day=ISSUED_ON.day + 1),
                narcotic_category=NarcoticCategory.NARCOTIC,
            ),
        )
        use_case = _use_case(fixture, catalog)

        # Act: 麻薬情報を付けずに登録する
        actual = await use_case.execute(_command(fixture))

        # Assert: 交付日時点では麻薬ではないので通る
        assert actual.management_info.narcotic_license_number is None
