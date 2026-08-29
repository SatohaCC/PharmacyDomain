"""処方箋の状態遷移と取得ユースケースのテスト。

「疑義照会中」を状態として持たない設計（未回答があるかは導出）を、
UseCase 経由でも固定する。
"""

from __future__ import annotations

import pytest

from app.application.prescription import (
    CancelPrescriptionCommand,
    GetPrescriptionQuery,
    PrescriptionDto,
    PrescriptionNotFoundError,
    ReadyForDispensingCommand,
    ResolveInquiryCommand,
    StartInquiryCommand,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription import (
    OpenInquiryExistsError,
    PrescriptionId,
    PrescriptionStatus,
    PrescriptionStatusTransitionError,
)
from tests.application.prescription.helpers import (
    PrescriptionFixture,
    create_fixture,
    create_register_command,
)


async def _register(fixture: PrescriptionFixture) -> PrescriptionDto:
    """検証済みの処方箋を1件登録する。"""
    return await fixture.register.execute(
        create_register_command(
            corporate_id=fixture.corporate_id,
            store_id=fixture.store_id,
            patient_id=fixture.patient_id,
        )
    )


async def _start_inquiry(fixture: PrescriptionFixture, prescription_id: str) -> None:
    """疑義照会を1件開始する。"""
    await fixture.start_inquiry.execute(
        StartInquiryCommand(
            corporate_id=str(fixture.corporate_id.value),
            prescription_id=prescription_id,
            pharmacist_id=str(fixture.pharmacist_id.value),
            category="dosage",
            content="1日3錠は用量超過ではないか確認したい。",
        )
    )


async def _resolve_inquiry(fixture: PrescriptionFixture, prescription_id: str) -> None:
    """疑義照会に回答する。"""
    await fixture.resolve_inquiry.execute(
        ResolveInquiryCommand(
            corporate_id=str(fixture.corporate_id.value),
            prescription_id=prescription_id,
            inquiry_number=1,
            responded_by="佐藤 一郎",
            result_type="unchanged",
            content="処方どおりで問題ない旨の回答を得た。",
        )
    )


def _ready_command(
    fixture: PrescriptionFixture, prescription_id: str
) -> ReadyForDispensingCommand:
    """調剤可能化コマンドを組み立てる。"""
    return ReadyForDispensingCommand(
        corporate_id=str(fixture.corporate_id.value),
        prescription_id=prescription_id,
    )


def _cancel_command(
    fixture: PrescriptionFixture, prescription_id: str
) -> CancelPrescriptionCommand:
    """取消コマンドを組み立てる。"""
    return CancelPrescriptionCommand(
        corporate_id=str(fixture.corporate_id.value),
        prescription_id=prescription_id,
    )


class Test調剤可能化:
    """未回答の照会があるうちは調剤可能へ進めない。"""

    async def test_照会が無ければ_調剤可能にできる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)

        # Act
        actual = await fixture.ready_for_dispensing.execute(
            _ready_command(fixture, registered.id)
        )

        # Assert
        assert actual.status == PrescriptionStatus.READY_FOR_DISPENSING.value

    async def test_未回答の照会があると_調剤可能にできない(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await _start_inquiry(fixture, registered.id)

        # Act / Assert
        with pytest.raises(OpenInquiryExistsError):
            await fixture.ready_for_dispensing.execute(
                _ready_command(fixture, registered.id)
            )

    async def test_照会に回答すれば_調剤可能にできる(self) -> None:
        """「疑義照会中」という状態を持たずに、導出だけで進めることを固定する。"""
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await _start_inquiry(fixture, registered.id)
        await _resolve_inquiry(fixture, registered.id)

        # Act
        actual = await fixture.ready_for_dispensing.execute(
            _ready_command(fixture, registered.id)
        )

        # Assert
        assert actual.status == PrescriptionStatus.READY_FOR_DISPENSING.value
        assert not actual.has_open_inquiry


class Test取消:
    """終端状態からは動かせない。"""

    async def test_受付済から_取消できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)

        # Act
        actual = await fixture.cancel.execute(_cancel_command(fixture, registered.id))

        # Assert
        assert actual.status == PrescriptionStatus.CANCELLED.value

    async def test_調剤可能からも_取消できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.ready_for_dispensing.execute(
            _ready_command(fixture, registered.id)
        )

        # Act
        actual = await fixture.cancel.execute(_cancel_command(fixture, registered.id))

        # Assert
        assert actual.status == PrescriptionStatus.CANCELLED.value

    async def test_取消済みは_再度取消できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.cancel.execute(_cancel_command(fixture, registered.id))

        # Act / Assert
        with pytest.raises(PrescriptionStatusTransitionError):
            await fixture.cancel.execute(_cancel_command(fixture, registered.id))

    async def test_取消済みは_調剤可能にできない(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.cancel.execute(_cancel_command(fixture, registered.id))

        # Act / Assert
        with pytest.raises(PrescriptionStatusTransitionError):
            await fixture.ready_for_dispensing.execute(
                _ready_command(fixture, registered.id)
            )


class Test取得:
    """エンティティを直接返さず、DTOで返す。"""

    async def test_登録した処方箋を_DTOで取得できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)

        # Act
        actual = await fixture.get.execute(
            GetPrescriptionQuery(
                corporate_id=str(fixture.corporate_id.value),
                prescription_id=registered.id,
            )
        )

        # Assert
        assert isinstance(actual, PrescriptionDto)
        assert actual.id == registered.id
        assert actual.medical_institution.name == "医療法人 サンプル病院"
        assert actual.prescriber.full_name_kana == "サトウ イチロウ"

    async def test_他法人からは_存在を隠して404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)

        # Act / Assert
        with pytest.raises(PrescriptionNotFoundError):
            await fixture.get.execute(
                GetPrescriptionQuery(
                    corporate_id=str(CorporateId.generate().value),
                    prescription_id=registered.id,
                )
            )

    async def test_存在しない処方箋は_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()

        # Act / Assert
        with pytest.raises(PrescriptionNotFoundError):
            await fixture.get.execute(
                GetPrescriptionQuery(
                    corporate_id=str(fixture.corporate_id.value),
                    prescription_id=str(PrescriptionId.generate().value),
                )
            )
