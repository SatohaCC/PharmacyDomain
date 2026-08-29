"""疑義照会ユースケース（開始・回答）のテスト。

主眼は2つ。

1. 実施者の薬剤師資格が UseCase から必ず検証されること
2. 照会日時・回答日時が**Commandではなく注入Clock**から来ること
   （呼び出し元が過去日時を詐称できない）
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.prescription import (
    PrescriptionDto,
    PrescriptionNotFoundError,
    PrescriptionPharmacistNotFoundError,
    ResolveInquiryCommand,
    StartInquiryCommand,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.prescription import (
    InquiryAlreadyResolvedError,
    InquiryNotFoundError,
    InquiryPharmacistQualificationError,
    PrescriptionId,
)
from app.domain.staff.primitives import StaffId, StaffQualifications
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


def _start_command(
    fixture: PrescriptionFixture,
    prescription_id: str,
    *,
    pharmacist_id: StaffId | None = None,
    content: str = "1日3錠は用量超過ではないか確認したい。",
) -> StartInquiryCommand:
    """疑義照会開始コマンドを組み立てる。"""
    return StartInquiryCommand(
        corporate_id=str(fixture.corporate_id.value),
        prescription_id=prescription_id,
        pharmacist_id=str(
            (
                pharmacist_id if pharmacist_id is not None else fixture.pharmacist_id
            ).value
        ),
        category="dosage",
        content=content,
    )


class Test疑義照会の開始:
    """資格の判定はDomain Service、資格の取得はBoundaryが担う。"""

    async def test_薬剤師が照会を開始すると_未回答で記録される(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)

        # Act
        actual = await fixture.start_inquiry.execute(
            _start_command(fixture, registered.id)
        )

        # Assert
        assert len(actual.inquiries) == 1
        assert actual.inquiries[0].inquiry_number == 1
        assert actual.inquiries[0].is_open
        assert actual.has_open_inquiry

    async def test_照会日時は_Commandではなく注入Clockから来る(self) -> None:
        """Commandに日時を持たせない設計を、時計を進めることで固定する。"""
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.start_inquiry.execute(_start_command(fixture, registered.id))
        fixture.clock.advance(timedelta(hours=2))

        # Act
        actual = await fixture.start_inquiry.execute(
            _start_command(fixture, registered.id, content="残薬の有無も確認したい。")
        )

        # Assert
        first, second = actual.inquiries
        assert datetime.fromisoformat(second.inquired_at) - datetime.fromisoformat(
            first.inquired_at
        ) == timedelta(hours=2)
        assert datetime.fromisoformat(second.inquired_at).tzinfo is not None

    async def test_薬剤師資格が無いスタッフは_照会を開始できない(self) -> None:
        """薬剤師法第24条。医療事務・調剤補助が実施者になってはならない。"""
        # Arrange
        fixture = create_fixture()
        clerk_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )
        registered = await _register(fixture)

        # Act / Assert
        with pytest.raises(InquiryPharmacistQualificationError):
            await fixture.start_inquiry.execute(
                _start_command(fixture, registered.id, pharmacist_id=clerk_id)
            )

    async def test_在籍していないスタッフは_存在を隠して404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)

        # Act / Assert
        with pytest.raises(PrescriptionPharmacistNotFoundError):
            await fixture.start_inquiry.execute(
                _start_command(fixture, registered.id, pharmacist_id=StaffId.generate())
            )

    async def test_存在しない処方箋への照会は_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()

        # Act / Assert
        with pytest.raises(PrescriptionNotFoundError):
            await fixture.start_inquiry.execute(
                _start_command(fixture, str(PrescriptionId.generate().value))
            )

    async def test_他法人から参照した処方箋は_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        command = StartInquiryCommand(
            corporate_id=str(CorporateId.generate().value),
            prescription_id=registered.id,
            pharmacist_id=str(fixture.pharmacist_id.value),
            category="dosage",
            content="用量を確認したい。",
        )

        # Act / Assert
        with pytest.raises(PrescriptionNotFoundError):
            await fixture.start_inquiry.execute(command)


class Test疑義照会への回答:
    """回答は1度だけ記録できる。"""

    @staticmethod
    def _resolve_command(
        fixture: PrescriptionFixture,
        prescription_id: str,
        *,
        inquiry_number: int = 1,
        result_type: str = "unchanged",
    ) -> ResolveInquiryCommand:
        """回答コマンドを組み立てる。"""
        return ResolveInquiryCommand(
            corporate_id=str(fixture.corporate_id.value),
            prescription_id=prescription_id,
            inquiry_number=inquiry_number,
            responded_by="佐藤 一郎",
            result_type=result_type,
            content="処方どおりで問題ない旨の回答を得た。",
        )

    async def test_回答すると_未回答ではなくなる(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.start_inquiry.execute(_start_command(fixture, registered.id))

        # Act
        actual = await fixture.resolve_inquiry.execute(
            self._resolve_command(fixture, registered.id)
        )

        # Assert
        assert not actual.has_open_inquiry
        assert actual.inquiries[0].response is not None
        assert actual.inquiries[0].response.responded_by == "佐藤 一郎"

    async def test_回答日時も_注入Clockから来る(self) -> None:
        # Arrange
        fixture = create_fixture(register_medicine=True)
        registered = await _register(fixture)
        await fixture.start_inquiry.execute(_start_command(fixture, registered.id))
        fixture.clock.advance(timedelta(minutes=30))

        # Act
        actual = await fixture.resolve_inquiry.execute(
            self._resolve_command(fixture, registered.id)
        )

        # Assert
        response = actual.inquiries[0].response
        assert response is not None
        assert datetime.fromisoformat(response.responded_at) == datetime(
            2026, 8, 23, 3, 30, tzinfo=UTC
        )

    async def test_回答済みの照会には_再度回答できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.start_inquiry.execute(_start_command(fixture, registered.id))
        await fixture.resolve_inquiry.execute(
            self._resolve_command(fixture, registered.id)
        )

        # Act / Assert
        with pytest.raises(InquiryAlreadyResolvedError):
            await fixture.resolve_inquiry.execute(
                self._resolve_command(fixture, registered.id)
            )

    async def test_存在しない照会番号への回答は_拒否される(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.start_inquiry.execute(_start_command(fixture, registered.id))

        # Act / Assert
        with pytest.raises(InquiryNotFoundError):
            await fixture.resolve_inquiry.execute(
                self._resolve_command(fixture, registered.id, inquiry_number=2)
            )

    async def test_処方削除の回答は_調剤不可として記録される(self) -> None:
        # Arrange
        fixture = create_fixture()
        registered = await _register(fixture)
        await fixture.start_inquiry.execute(_start_command(fixture, registered.id))

        # Act
        actual = await fixture.resolve_inquiry.execute(
            self._resolve_command(fixture, registered.id, result_type="deleted")
        )

        # Assert
        response = actual.inquiries[0].response
        assert response is not None
        assert response.blocks_dispensing
