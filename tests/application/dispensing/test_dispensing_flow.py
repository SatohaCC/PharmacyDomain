"""調剤ユースケースのテスト。

主眼は3つ。

1. 認可と法人境界（他法人の店舗・処方箋・スタッフは404相当に畳む）
2. 調剤回数・日付・変更制限・薬剤師資格・剤対応など、集約を跨ぐ検証が
   UseCase から**必ず**呼ばれること
3. 処方箋を調剤済へ進める契機が**調剤終了区分**であること
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.application.access_control import TenantBoundaryNotFoundError
from app.application.corporate.exceptions import CorporateInactiveError
from app.application.dispensing import (
    CompleteDispensingCommand,
    DispensingNotFoundError,
    DispensingPrescriptionNotFoundError,
    DispensingStaffNotFoundError,
    DispensingStoreNotFoundError,
    GetDispensingQuery,
    GetDispensingUseCase,
    ListDispensingsByPrescriptionQuery,
    PrescriptionNotReadyForDispensingError,
    RecordAuditCommand,
    RecordDispensedContentCommand,
    VerifyDispensingCommand,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.dispensing import (
    DispensedRpNotInPrescriptionError,
    DispensingAlreadyExistsError,
    DispensingId,
    DispensingOutsidePrescriptionPeriodError,
    DispensingPharmacistQualificationError,
    DispensingProcessStatus,
    IterationExceedsInstructionError,
    PreviousDispensingUnknownError,
    SelfVerificationNotAllowedError,
    SubstitutionNotAllowedError,
    VerificationNotPassedError,
)
from app.domain.prescription import (
    GenericSubstitutionRestrictionType,
    PrescriptionManagementInfo,
    PrescriptionStatus,
    RefillCount,
    RefillInstruction,
)
from app.domain.staff.primitives import StaffId, StaffQualifications
from tests.application.dispensing.helpers import (
    DispensingFixture,
    create_actor_access,
    create_fixture,
    create_medicine_input,
    create_rp_input,
    create_start_command,
    create_substituted_medicine_input,
)
from tests.factories.dispensing_factory import DISPENSED_ON
from tests.factories.prescription_factory import (
    create_medicine,
    create_prescription,
    create_rp,
)

_NEXT_DATE = date(2026, 9, 21)


def _refill_management_info() -> PrescriptionManagementInfo:
    """リフィル3回の処方箋管理情報を組み立てる。"""
    return PrescriptionManagementInfo(
        refill=RefillInstruction(total_refill_count=RefillCount(3))
    )


async def _start(fixture: DispensingFixture) -> str:
    """既定の調剤セッションを1件開始し、そのIDを返す。"""
    started = await fixture.start.execute(create_start_command(fixture))
    return started.id


async def _verify_passed(fixture: DispensingFixture, dispensing_id: str) -> None:
    """最終鑑査に合格させる。"""
    await fixture.verify.execute(
        VerifyDispensingCommand(
            corporate_id=str(fixture.corporate_id.value),
            dispensing_id=dispensing_id,
            verifier_id=str(fixture.verifier_id.value),
            result="passed",
        )
    )


class Test調剤の開始:
    """処方箋・担当者・回数の整合を確認して開始する。"""

    async def test_調剤を開始すると_調製中で保存される(self) -> None:
        # Arrange
        fixture = create_fixture()

        # Act
        actual = await fixture.start.execute(create_start_command(fixture))

        # Assert
        assert actual.status == DispensingProcessStatus.IN_PROGRESS.value
        assert actual.iteration == 1
        assert actual.patient_id == str(fixture.prescription.patient_id.value)
        stored = await fixture.repository.get(
            corporate_id=fixture.corporate_id,
            dispensing_id=DispensingId.parse(actual.id),
        )
        assert stored is not None

    async def test_患者は処方箋から決まる(self) -> None:
        """Commandに患者IDを持たせない。処方箋と食い違う患者を指定できてしまう。"""
        # Arrange
        fixture = create_fixture()
        command = create_start_command(fixture)

        # Act
        actual = await fixture.start.execute(command)

        # Assert
        assert not hasattr(command, "patient_id")
        assert actual.patient_id == str(fixture.prescription.patient_id.value)

    async def test_処方内容が確定していないと_開始できない(self) -> None:
        """未回答の疑義照会があるうちは処方内容が確定していない。"""
        # Arrange
        fixture = create_fixture()
        received = fixture.prescription.return_for_inquiry()
        fixture.prescription_source.register(received)

        # Act / Assert
        with pytest.raises(PrescriptionNotReadyForDispensingError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_小数の用量が_丸められずに文字列で返る(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_start_command(
            fixture,
            dispensed_rps=(
                create_rp_input(
                    medicines=(create_medicine_input(amount="0.05", unit="g"),)
                ),
            ),
        )

        # Act
        actual = await fixture.start.execute(command)

        # Assert
        assert actual.dispensed_rps[0].medicines[0].amount == "0.05"
        assert Decimal(actual.dispensed_rps[0].medicines[0].amount) == Decimal("0.05")

    async def test_同じ回数の調剤は_二重に開始できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        await fixture.start.execute(create_start_command(fixture))

        # Act / Assert
        with pytest.raises(DispensingAlreadyExistsError):
            await fixture.start.execute(create_start_command(fixture))


class Test認可と法人境界:
    """他テナントは403ではなく404に畳む。"""

    async def test_無効な法人では_開始できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.corporate_repository.set_inactive(fixture.corporate_id)

        # Act / Assert
        with pytest.raises(CorporateInactiveError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_別法人の店舗を指定すると_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.store_reference.registered.clear()

        # Act / Assert
        with pytest.raises(DispensingStoreNotFoundError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_別法人の処方箋を指定すると_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        fixture.prescription_source.prescriptions.clear()

        # Act / Assert
        with pytest.raises(DispensingPrescriptionNotFoundError):
            await fixture.start.execute(create_start_command(fixture))

    async def test_在籍していないスタッフは_404相当になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_start_command(fixture, dispenser_id=StaffId.generate())

        # Act / Assert
        with pytest.raises(DispensingStaffNotFoundError):
            await fixture.start.execute(command)

    async def test_他法人からは_調剤セッションを取得できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act / Assert
        with pytest.raises(DispensingNotFoundError):
            await fixture.get.execute(
                GetDispensingQuery(
                    corporate_id=str(CorporateId.generate().value),
                    dispensing_id=dispensing_id,
                )
            )


class Test薬剤師資格:
    """薬剤師法第19条に基づく調剤者の資格を検証する。"""

    async def test_薬剤師資格が無いと_調剤できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        clerk_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )

        # Act / Assert
        with pytest.raises(DispensingPharmacistQualificationError, match="調剤者"):
            await fixture.start.execute(
                create_start_command(fixture, dispenser_id=clerk_id)
            )

    async def test_薬剤師資格が無いと_最終鑑査できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)
        clerk_id = StaffId.generate()
        fixture.staff_qualification.register(
            corporate_id=fixture.corporate_id,
            staff_id=clerk_id,
            qualifications=StaffQualifications.empty(),
        )

        # Act / Assert
        with pytest.raises(DispensingPharmacistQualificationError, match="最終鑑査者"):
            await fixture.verify.execute(
                VerifyDispensingCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    dispensing_id=dispensing_id,
                    verifier_id=str(clerk_id.value),
                    result="passed",
                )
            )

    async def test_調剤者本人は_最終鑑査できない(self) -> None:
        """管理薬剤師による一括代行署名の禁止。"""
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act / Assert
        with pytest.raises(SelfVerificationNotAllowedError):
            await fixture.verify.execute(
                VerifyDispensingCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    dispensing_id=dispensing_id,
                    verifier_id=str(fixture.dispenser_id.value),
                    result="passed",
                )
            )


class Test処方箋との整合:
    """Domain Service が UseCase から呼ばれていること。"""

    async def test_処方箋に無い剤を調剤すると_開始できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_start_command(
            fixture, dispensed_rps=(create_rp_input(rp_number=2),)
        )

        # Act / Assert
        with pytest.raises(DispensedRpNotInPrescriptionError):
            await fixture.start.execute(command)

    async def test_使用期限を過ぎた1回目は_開始できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_start_command(fixture, dispensed_on=date(2026, 8, 28))

        # Act / Assert
        with pytest.raises(DispensingOutsidePrescriptionPeriodError):
            await fixture.start.execute(command)

    async def test_通常処方箋の2回目は_開始できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        command = create_start_command(fixture, iteration=2)

        # Act / Assert: 回数超過が先に検出される
        with pytest.raises(IterationExceedsInstructionError):
            await fixture.start.execute(command)

    async def test_前回セッションが無い2回目は_開始できない(self) -> None:
        """リフィル処方箋で自局に前回の記録が無いケース。素通りさせない。"""
        # Arrange
        fixture = create_fixture(
            prescription=create_prescription(
                management_info=_refill_management_info(),
            )
        )
        command = create_start_command(fixture, iteration=2, dispensed_on=_NEXT_DATE)

        # Act / Assert
        with pytest.raises(PreviousDispensingUnknownError):
            await fixture.start.execute(command)

    async def test_変更制限に反する代替調剤は_開始できない(self) -> None:
        # Arrange
        fixture = create_fixture(
            prescription=create_prescription(
                rps=(
                    create_rp(
                        medicines=(
                            create_medicine(
                                restriction=(
                                    GenericSubstitutionRestrictionType.NO_GENERIC
                                )
                            ),
                        )
                    ),
                )
            )
        )
        command = create_start_command(
            fixture,
            dispensed_rps=(
                create_rp_input(medicines=(create_substituted_medicine_input(),)),
            ),
        )

        # Act / Assert
        with pytest.raises(SubstitutionNotAllowedError):
            await fixture.start.execute(command)

    async def test_変更制限に反する代替調剤は_後から差し替えても拒否される(
        self,
    ) -> None:
        """開始時だけの検証にすると、後から差し替えて回避できてしまう。"""
        # Arrange
        fixture = create_fixture(
            prescription=create_prescription(
                rps=(
                    create_rp(
                        medicines=(
                            create_medicine(
                                restriction=(
                                    GenericSubstitutionRestrictionType.NO_GENERIC
                                )
                            ),
                        )
                    ),
                )
            )
        )
        dispensing_id = await _start(fixture)

        # Act / Assert
        with pytest.raises(SubstitutionNotAllowedError):
            await fixture.record_content.execute(
                RecordDispensedContentCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    dispensing_id=dispensing_id,
                    dispensed_rps=(
                        create_rp_input(
                            medicines=(create_substituted_medicine_input(),)
                        ),
                    ),
                )
            )


class Test変更調剤の記録:
    """3軸をそのまま記録する。加算の算定可否は判定しない。"""

    async def test_後発品への変更を_記録できる(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act
        actual = await fixture.record_content.execute(
            RecordDispensedContentCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                dispensed_rps=(
                    create_rp_input(medicines=(create_substituted_medicine_input(),)),
                ),
            )
        )

        # Assert
        substitution = actual.dispensed_rps[0].medicines[0].substitution
        assert substitution is not None
        assert substitution.category == "generic_substitution"

    async def test_一包化と自家製剤を_同時に記録できる(self) -> None:
        """加算の排他は Claim の責務。ここで排他にすると事実を残せない。"""
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act
        actual = await fixture.record_content.execute(
            RecordDispensedContentCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                dispensed_rps=(
                    create_rp_input(
                        medicines=(
                            create_medicine_input(
                                preparations=("unit_dose_packaged", "compounded")
                            ),
                        )
                    ),
                ),
            )
        )

        # Assert
        assert actual.dispensed_rps[0].medicines[0].preparations == (
            "unit_dose_packaged",
            "compounded",
        )


class Test鑑査と完了:
    """処方鑑査（前）→ 最終鑑査（後）→ 交付。"""

    async def test_処方鑑査を記録しても_状態は動かない(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act
        actual = await fixture.record_audit.execute(
            RecordAuditCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                auditor_id=str(fixture.verifier_id.value),
                has_issues=False,
            )
        )

        # Assert
        assert actual.audit is not None
        assert actual.status == DispensingProcessStatus.IN_PROGRESS.value

    async def test_鑑査日時は_Commandではなく注入Clockから来る(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)
        fixture.clock.advance(timedelta(hours=3))

        # Act
        actual = await fixture.record_audit.execute(
            RecordAuditCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                auditor_id=str(fixture.verifier_id.value),
                has_issues=False,
            )
        )

        # Assert
        assert actual.audit is not None
        assert actual.audit.audited_at.startswith("2026-08-23T06:00")

    async def test_鑑査不合格なら_調製中のまま留まる(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act
        actual = await fixture.verify.execute(
            VerifyDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                verifier_id=str(fixture.verifier_id.value),
                result="failed",
                notes="秤量が処方と一致しない。",
            )
        )

        # Assert
        assert actual.status == DispensingProcessStatus.IN_PROGRESS.value
        assert actual.verification is not None
        assert actual.verification.result == "failed"

    async def test_鑑査に合格していないと_完了できない(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)

        # Act / Assert
        with pytest.raises(VerificationNotPassedError):
            await fixture.complete.execute(
                CompleteDispensingCommand(
                    corporate_id=str(fixture.corporate_id.value),
                    dispensing_id=dispensing_id,
                    completion_type="completed",
                )
            )


class Test処方箋の調剤済への遷移:
    """契機は調剤終了区分であり、調剤回数ではない。"""

    async def test_調剤終了なら_処方箋が調剤済になる(self) -> None:
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)
        await _verify_passed(fixture, dispensing_id)

        # Act
        actual = await fixture.complete.execute(
            CompleteDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                completion_type="completed",
            )
        )

        # Assert
        assert actual.status == DispensingProcessStatus.COMPLETED.value
        prescription = await fixture.prescription_source.get_or_raise(
            corporate_id=fixture.corporate_id,
            prescription_id=fixture.prescription.id,
        )
        assert prescription.status is PrescriptionStatus.DISPENSED

    async def test_調剤継続なら_処方箋は調剤済にならない(self) -> None:
        """次回以降の調剤が残っているので、処方箋はまだ終わっていない。"""
        # Arrange
        fixture = create_fixture(
            prescription=create_prescription(management_info=_refill_management_info())
        )
        dispensing_id = await _start(fixture)
        await _verify_passed(fixture, dispensing_id)

        # Act
        actual = await fixture.complete.execute(
            CompleteDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                completion_type="continues",
                next_dispensing_date=_NEXT_DATE,
            )
        )

        # Assert
        assert actual.next_dispensing_date == _NEXT_DATE.isoformat()
        prescription = await fixture.prescription_source.get_or_raise(
            corporate_id=fixture.corporate_id,
            prescription_id=fixture.prescription.id,
        )
        assert prescription.status is PrescriptionStatus.READY_FOR_DISPENSING

    async def test_総使用回数に達していなくても_終了にできる(self) -> None:
        """規格は「達していないが次回以降の調剤が不要となった場合」も終了と定める。"""
        # Arrange
        fixture = create_fixture(
            prescription=create_prescription(management_info=_refill_management_info())
        )
        dispensing_id = await _start(fixture)
        await _verify_passed(fixture, dispensing_id)

        # Act
        await fixture.complete.execute(
            CompleteDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
                completion_type="completed",
            )
        )

        # Assert
        prescription = await fixture.prescription_source.get_or_raise(
            corporate_id=fixture.corporate_id,
            prescription_id=fixture.prescription.id,
        )
        assert prescription.status is PrescriptionStatus.DISPENSED


class Test一覧と取得:
    """自局実施分のみ。件数から総調剤回数を導出してはならない。"""

    async def test_調剤回数の昇順で一覧できる(self) -> None:
        # Arrange
        fixture = create_fixture(
            prescription=create_prescription(management_info=_refill_management_info())
        )
        first = await fixture.start.execute(create_start_command(fixture))
        await _verify_passed(fixture, first.id)
        await fixture.complete.execute(
            CompleteDispensingCommand(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=first.id,
                completion_type="continues",
                next_dispensing_date=_NEXT_DATE,
            )
        )
        await fixture.start.execute(
            create_start_command(fixture, iteration=2, dispensed_on=_NEXT_DATE)
        )

        # Act
        actual = await fixture.list_by_prescription.execute(
            ListDispensingsByPrescriptionQuery(
                corporate_id=str(fixture.corporate_id.value),
                prescription_id=str(fixture.prescription.id.value),
            )
        )

        # Assert
        assert [item.iteration for item in actual] == [1, 2]

    async def test_他法人からは_一覧に現れない(self) -> None:
        # Arrange
        fixture = create_fixture()
        await _start(fixture)

        # Act: 別法人IDで問い合わせる
        actual = await fixture.list_by_prescription.execute(
            ListDispensingsByPrescriptionQuery(
                corporate_id=str(CorporateId.generate().value),
                prescription_id=str(fixture.prescription.id.value),
            )
        )

        # Assert
        assert actual == ()

    async def test_法人管理者は_他法人の調剤を参照できない(self) -> None:
        """処方箋と同じく、他テナントは404相当（``TenantBoundaryNotFoundError``）。"""
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)
        use_case = GetDispensingUseCase(
            fixture.repository,
            create_actor_access(fixture.corporate_repository, fixture.corporate_id),
        )

        # Act / Assert
        with pytest.raises(TenantBoundaryNotFoundError):
            await use_case.execute(
                GetDispensingQuery(
                    corporate_id=str(CorporateId.generate().value),
                    dispensing_id=dispensing_id,
                )
            )

    async def test_法人管理者は_自法人の調剤を参照できる(self) -> None:
        """調剤の権限が法人管理者に与えられていることを固定する。"""
        # Arrange
        fixture = create_fixture()
        dispensing_id = await _start(fixture)
        use_case = GetDispensingUseCase(
            fixture.repository,
            create_actor_access(fixture.corporate_repository, fixture.corporate_id),
        )

        # Act
        actual = await use_case.execute(
            GetDispensingQuery(
                corporate_id=str(fixture.corporate_id.value),
                dispensing_id=dispensing_id,
            )
        )

        # Assert
        assert actual.id == dispensing_id


def test_調剤日の既定値が_処方箋の使用期間内である() -> None:
    """ファクトリの既定値が期間外になると、他のテストが理由なく落ちる。"""
    # Arrange / Act
    prescription = create_prescription()

    # Assert
    assert prescription.period.includes(DISPENSED_ON)
