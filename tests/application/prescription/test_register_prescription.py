"""処方箋登録ユースケースのテスト。

このファイルの主眼は3つある。

1. 認可と法人境界（他法人の店舗・患者は404相当に畳む）
2. 麻薬・リフィル・公費負担など、集約を跨ぐ検証が UseCase から**必ず**呼ばれること
3. 医薬品マスタが無い状態で「該当しない」と黙って答えないこと（fail-closed）
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.application.access_control import TenantBoundaryNotFoundError
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.prescription import (
    PrescriptionCoverageSelectionNotFoundError,
    PrescriptionManagementInput,
    PrescriptionPatientNotFoundError,
    PrescriptionStoreNotFoundError,
    PublicExpenseBurdenInput,
)
from app.base.domain.medicine import (
    MedicineCodeType,
    PublicExpenseBurden,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription import (
    MedicineClassificationMissingError,
    MedicineClassificationUnknownError,
    MedicineCodeTypeNotAllowedError,
    MedicineRestrictionFlag,
    NarcoticPrescriptionDetailsRequiredError,
    PrescriptionDocumentNumberAlreadyExistsError,
    PrescriptionId,
    PrescriptionStatus,
    PublicExpenseBurdenNotCoveredError,
    RefillNotAllowedError,
)
from app.domain.reception.primitives import CoverageSelectionRecordId
from app.domain.store.primitives import StoreId
from tests.application.prescription.helpers import (
    ISSUED_ON,
    create_classification,
    create_fixture,
    create_medicine_input,
    create_register_command,
    create_rp_input,
)

_NARCOTIC_INPUT = PrescriptionManagementInput(
    narcotic_license_number="13-1234",
    patient_address="東京都千代田区1-2-3",
    patient_phone_number="0312345678",
)


class Test正常系:
    """境界がすべて満たされたときの登録。"""

    async def test_処方箋を登録すると_受付済で保存される(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.status == PrescriptionStatus.RECEIVED.value
        assert actual.corporate_id == str(fixture.corporate_id.value)
        stored = await fixture.repository.get(
            corporate_id=fixture.corporate_id,
            prescription_id=PrescriptionId.parse(actual.id),
        )
        assert stored is not None

    async def test_使用期限を省略すると_交付日を含めて4日間になる(self) -> None:
        """保険調剤の理解のために（令和8年度）の既定値。"""
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            valid_to=None,
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.period.issued_date == ISSUED_ON.isoformat()
        assert actual.period.valid_to == date(2026, 8, 27).isoformat()

    async def test_小数の用量が_丸められずに文字列で返る(self) -> None:
        """用量は ``Decimal`` で保持し、DTOでも文字列のまま返す。

        ``float`` を経由すると 0.05刻みの用量が丸められ、不均等服用の
        合計一致という不変条件を呼び出し元が再現できなくなる。
        """
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            rps=(
                create_rp_input(
                    medicines=(create_medicine_input(amount="0.05", unit="g"),)
                ),
            ),
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.rps[0].medicines[0].amount == "0.05"
        assert Decimal(actual.rps[0].medicines[0].amount) == Decimal("0.05")


class Test認可と法人境界:
    """AGENTS.md「テナント境界」。他テナントは403ではなく404に畳む。"""

    async def test_法人管理者は_自法人の処方箋を登録できる(self) -> None:
        """処方箋の権限が法人管理者に与えられていることを固定する。

        ``Permission`` へ足しただけで ``policy.py`` の集合へ足し忘れると
        import 時に ``RuntimeError`` になるが、ベンダー専用側へ入れてしまった
        場合はそれでは気づけない。法人管理者の向きでも1本固定する。
        """
        # Arrange
        fixture = create_fixture(as_corporate_admin=True)
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.status == PrescriptionStatus.RECEIVED.value

    async def test_法人管理者は_他法人の処方箋を登録できない(self) -> None:
        """他テナントは403ではなく404相当（``TenantBoundaryNotFoundError``）。"""
        # Arrange
        fixture = create_fixture(as_corporate_admin=True)
        command = create_register_command(
            corporate_id=CorporateId.generate(),
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act / Assert
        with pytest.raises(TenantBoundaryNotFoundError):
            await fixture.register.execute(command)

    async def test_無効な法人では_登録できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.corporate_repository.set_inactive(fixture.corporate_id)
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act / Assert
        with pytest.raises(CorporateInactiveError):
            await fixture.register.execute(command)

    async def test_別法人の店舗を指定すると_存在を隠して404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=StoreId.generate(),
            patient_id=fixture.patient_id,
        )

        # Act / Assert
        with pytest.raises(PrescriptionStoreNotFoundError):
            await fixture.register.execute(command)

    async def test_別法人の患者を指定すると_存在を隠して404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=PatientId.generate(),
        )

        # Act / Assert
        with pytest.raises(PrescriptionPatientNotFoundError):
            await fixture.register.execute(command)

    async def test_他法人の処方箋は_取得できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await fixture.register.execute(
            create_register_command(
                corporate_id=fixture.corporate_id,
                store_id=fixture.store_id,
                patient_id=fixture.patient_id,
            )
        )

        # Act
        actual = await fixture.repository.get(
            corporate_id=CorporateId.generate(),
            prescription_id=PrescriptionId.parse(registered.id),
        )

        # Assert
        assert actual is None


class Test引換番号の一意性:
    """電子処方箋のときだけ課す（受領元ごとの業務判断）。"""

    async def test_電子処方箋の引換番号が重複すると_登録できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            source_type="electronic",
        )
        await fixture.register.execute(command)

        # Act / Assert
        with pytest.raises(PrescriptionDocumentNumberAlreadyExistsError):
            await fixture.register.execute(command)

    async def test_紙処方箋は_同じ番号でも登録できる(self) -> None:
        """紙の番号は医療機関ごとの採番なので法人内で衝突しうる。"""
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            source_type="paper_qr",
        )
        first = await fixture.register.execute(command)

        # Act
        second = await fixture.register.execute(command)

        # Assert
        assert first.id != second.id
        assert first.document_number == second.document_number


class Test医薬品マスタのfail_closed:
    """衝突3の解決が UseCase 経由でも効いていることを固定する。"""

    async def test_マスタ未登録の薬品は_問題なしにせず拒否される(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act / Assert
        with pytest.raises(MedicineClassificationMissingError):
            await fixture.register.execute(command)

    async def test_麻薬区分が不明だと_該当しない扱いにせず拒否される(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        fixture.medicine_restriction.register(
            create_classification(is_narcotic=MedicineRestrictionFlag.UNKNOWN)
        )
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act / Assert
        with pytest.raises(MedicineClassificationUnknownError):
            await fixture.register.execute(command)

    async def test_麻薬を含むのに麻薬情報が無いと_登録できない(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        fixture.medicine_restriction.register(
            create_classification(is_narcotic=MedicineRestrictionFlag.YES)
        )
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )

        # Act / Assert
        with pytest.raises(NarcoticPrescriptionDetailsRequiredError):
            await fixture.register.execute(command)

    async def test_麻薬を含み麻薬情報が揃っていれば_登録できる(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        fixture.medicine_restriction.register(
            create_classification(is_narcotic=MedicineRestrictionFlag.YES)
        )
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            management_info=_NARCOTIC_INPUT,
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.management_info.narcotic_license_number == "13-1234"

    async def test_投与量に限度がある医薬品は_リフィルにできない(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=False)
        fixture.medicine_restriction.register(
            create_classification(has_dosage_limit=MedicineRestrictionFlag.YES)
        )
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            management_info=PrescriptionManagementInput(refill_count=3),
        )

        # Act / Assert
        with pytest.raises(RefillNotAllowedError):
            await fixture.register.execute(command)

    async def test_適用除外に当たらなければ_リフィルで登録できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            management_info=PrescriptionManagementInput(refill_count=3),
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.management_info.refill_count == 3


class Test公費負担の裏付け:
    """裏付けの無い公費負担を凍結させない。"""

    async def test_資格選択履歴が無いのに公費負担ありだと_拒否される(self) -> None:
        """履歴が無ければ裏付けの取りようがないので、枠なしとして検証する。

        「履歴が無ければ検証を飛ばす」実装にすると、履歴を付けないだけで
        裏付けの無い公費負担が通ってしまう。
        """
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            rps=(
                create_rp_input(
                    medicines=(
                        create_medicine_input(
                            public_expense_burden=PublicExpenseBurdenInput(first=True)
                        ),
                    )
                ),
            ),
        )

        # Act / Assert
        with pytest.raises(PublicExpenseBurdenNotCoveredError):
            await fixture.register.execute(command)

    async def test_資格に第一公費があれば_公費負担ありで登録できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        record_id = CoverageSelectionRecordId.generate()
        fixture.public_expense.register(
            corporate_id=fixture.corporate_id,
            patient_id=fixture.patient_id,
            coverage_selection_record_id=record_id,
            burden=PublicExpenseBurden(first=True),
        )
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            rps=(
                create_rp_input(
                    medicines=(
                        create_medicine_input(
                            public_expense_burden=PublicExpenseBurdenInput(first=True)
                        ),
                    )
                ),
            ),
            coverage_selection_record_id=str(record_id.value),
        )

        # Act
        actual = await fixture.register.execute(command)

        # Assert
        assert actual.rps[0].medicines[0].public_expense_burden is not None
        assert actual.rps[0].medicines[0].public_expense_burden.first
        assert actual.coverage_selection_record_id == str(record_id.value)

    async def test_存在しない資格選択履歴を指定すると_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            coverage_selection_record_id=str(
                CoverageSelectionRecordId.generate().value
            ),
        )

        # Act / Assert
        with pytest.raises(PrescriptionCoverageSelectionNotFoundError):
            await fixture.register.execute(command)


class Test集約の不変条件がUseCase経由でも効くこと:
    """UseCase が集約を素通りさせていないことを1つの向きで固定する。"""

    async def test_電子処方箋でHOTコードを使うと_登録できない(self) -> None:
        """処方編 別表15 は 3:厚生省コード と 6:HOTコード を「使用しない」と定める。"""
        # Arrange
        fixture = create_fixture()
        command = create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
            source_type="electronic",
            rps=(
                create_rp_input(
                    medicines=(
                        create_medicine_input(
                            code_type=MedicineCodeType.HOT.value, code="1234567"
                        ),
                    )
                ),
            ),
        )

        # Act / Assert
        with pytest.raises(MedicineCodeTypeNotAllowedError):
            await fixture.register.execute(command)
