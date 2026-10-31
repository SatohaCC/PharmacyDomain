"""スタッフ（Staff）の社会ルール・労働法・施設基準適合性に関するドメインテスト。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.corporate.identifiers import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import (
    EmploymentType,
    LeaveReason,
    StaffStatus,
    WeeklyContractHours,
)
from app.domain.staff.value_objects import (
    AffiliationPeriod,
    StaffQualifications,
    StoreAffiliation,
)
from app.domain.store.identifiers import StoreId


def _create_staff(
    *,
    employment_type: EmploymentType = EmploymentType.REGULAR,
    status: StaffStatus = StaffStatus.ACTIVE,
    leave_reason: LeaveReason | None = None,
    weekly_contract_hours: WeeklyContractHours | None = None,
    affiliations: tuple[StoreAffiliation, ...] = (),
) -> Staff:
    return Staff(
        id=StaffId.generate(),
        corporate_id=CorporateId.generate(),
        names=PersonNames(
            kanji=PersonName(
                last_name=PersonNamePart("佐藤"), first_name=PersonNamePart("花子")
            ),
            kana=PersonNameKana(
                last_name=PersonNameKanaPart("サトウ"),
                first_name=PersonNameKanaPart("ハナコ"),
            ),
        ),
        qualifications=StaffQualifications.empty(),
        employment_type=employment_type,
        status=status,
        leave_reason=leave_reason,
        weekly_contract_hours=weekly_contract_hours,
        affiliations=affiliations,
    )


# --- 1. 週契約労働時間 (WeeklyContractHours) のテスト ---


def test_週契約労働時間_有効な時間_正しく生成され常勤換算比率を算出できる() -> None:
    # Arrange: 週40時間（常勤フルタイム）
    hours_40 = WeeklyContractHours(Decimal("40.0"))

    # Act & Assert
    assert hours_40.value == Decimal("40.0")
    assert hours_40.full_time_equivalent() == Decimal("1.00")
    assert hours_40.is_full_time() is True


def test_週契約労働時間_パート短時間_常勤換算比率を算出できる() -> None:
    # Arrange: 週20時間パート
    hours_20 = WeeklyContractHours(Decimal("20.0"))

    # Act & Assert
    assert hours_20.full_time_equivalent() == Decimal("0.50")
    assert hours_20.is_full_time() is False


def test_週契約労働時間_ゼロ時間_ヘルプ応援の事前登録として許容される() -> None:
    # Arrange: スポット応援・ヘルプ要員の0時間登録
    hours_0 = WeeklyContractHours(Decimal("0.0"))

    # Act & Assert
    assert hours_0.value == Decimal("0.0")
    assert hours_0.full_time_equivalent() == Decimal("0.00")
    assert hours_0.is_full_time() is False


@pytest.mark.parametrize(
    ("invalid_val", "expected_err"),
    [
        (Decimal("-1.0"), "週所定労働時間は0以上の値である必要があります。"),
        (Decimal("80.5"), "週所定労働時間は80時間以内で指定してください。"),
    ],
)
def test_週契約労働時間_不正な値_エラーを送出する(
    invalid_val: Decimal, expected_err: str
) -> None:
    with pytest.raises(DomainValidationError) as exc_info:
        WeeklyContractHours(invalid_val)
    assert expected_err in str(exc_info.value)


# --- 2. 雇用形態 (EmploymentType) のテスト ---


def test_雇用形態_正社員_契約社員_パート_派遣_保持できる() -> None:
    # Arrange & Act
    regular = _create_staff(employment_type=EmploymentType.REGULAR)
    part_time = _create_staff(employment_type=EmploymentType.PART_TIME)
    dispatched = _create_staff(employment_type=EmploymentType.DISPATCHED)

    # Assert
    assert regular.employment_type == EmploymentType.REGULAR
    assert regular.employment_type.label == "正社員"
    assert part_time.employment_type == EmploymentType.PART_TIME
    assert part_time.employment_type.label == "パート・アルバイト"
    assert dispatched.employment_type == EmploymentType.DISPATCHED
    assert dispatched.employment_type.label == "派遣スタッフ"


# --- 3. 休職・復職 (Leave Management) のテスト ---


def test_スタッフ_休職開始_在籍を保ちながら休職状態かつ非稼働になる() -> None:
    # Arrange: 店舗所属を持つ稼働中のスタッフ
    store_id = StoreId.generate()
    affiliation = StoreAffiliation(
        store_id=store_id,
        period=AffiliationPeriod(start_date=date(2026, 1, 1)),
        is_primary=True,
    )
    staff = _create_staff(affiliations=(affiliation,))
    assert staff.is_active is True
    assert staff.status == StaffStatus.ACTIVE
    assert staff.is_on_leave is False

    # Act: 育児休業を開始
    on_leave_staff = staff.start_leave(
        reason=LeaveReason.CHILDCARE, left_on=date(2026, 4, 1)
    )

    # Assert
    assert on_leave_staff.status == StaffStatus.ON_LEAVE
    assert on_leave_staff.leave_reason == LeaveReason.CHILDCARE
    assert on_leave_staff.is_on_leave is True
    # 休職中は当日の調剤・鑑査業務を行えないため is_active は False になる
    assert on_leave_staff.is_active is False
    # 所属履歴（在籍）は退職と異なり打ち切られず維持される
    assert len(on_leave_staff.affiliations) == 1
    assert on_leave_staff.affiliations[0].period.end_date is None


def test_スタッフ_休職からの復職_稼働状態へ復帰する() -> None:
    # Arrange
    staff = _create_staff(
        status=StaffStatus.ON_LEAVE, leave_reason=LeaveReason.MATERNITY
    )
    assert staff.is_active is False

    # Act: 復職
    returned_staff = staff.return_from_leave()

    # Assert
    assert returned_staff.status == StaffStatus.ACTIVE
    assert returned_staff.leave_reason is None
    assert returned_staff.is_active is True
    assert returned_staff.is_on_leave is False


def test_スタッフ_休職理由なしで休職状態を構築_エラーを送出する() -> None:
    # Act / Assert
    with pytest.raises(DomainValidationError) as exc_info:
        _create_staff(status=StaffStatus.ON_LEAVE, leave_reason=None)
    assert "休職中のスタッフには休職理由が必要です" in str(exc_info.value)


# --- 4. 実効稼働時間と常勤換算比率 (Effective Hours & FTE) のテスト ---


def test_スタッフ_稼働中の実効稼働時間と常勤換算_契約時間通りに算出される() -> None:
    # Arrange: 週40時間の正社員
    full_time_staff = _create_staff(
        status=StaffStatus.ACTIVE,
        weekly_contract_hours=WeeklyContractHours(Decimal("40.0")),
    )
    # Arrange: 週20時間のパート
    part_time_staff = _create_staff(
        status=StaffStatus.ACTIVE,
        weekly_contract_hours=WeeklyContractHours(Decimal("20.0")),
    )

    # Act & Assert
    assert full_time_staff.effective_weekly_hours == Decimal("40.0")
    assert full_time_staff.effective_full_time_equivalent() == Decimal("1.00")
    assert full_time_staff.effective_is_full_time() is True

    assert part_time_staff.effective_weekly_hours == Decimal("20.0")
    assert part_time_staff.effective_full_time_equivalent() == Decimal("0.50")
    assert part_time_staff.effective_is_full_time() is False


def test_スタッフ_ゼロ時間ヘルプ登録_実効稼働時間と常勤換算はゼロになる() -> None:
    # Arrange: 厚生局事前届出済みのスポット応援（ヘルプ）登録（週0時間）
    help_staff = _create_staff(
        status=StaffStatus.ACTIVE,
        weekly_contract_hours=WeeklyContractHours(Decimal("0.0")),
    )

    # Act & Assert
    assert help_staff.effective_weekly_hours == Decimal("0.0")
    assert help_staff.effective_full_time_equivalent() == Decimal("0.00")
    assert help_staff.effective_is_full_time() is False


def test_スタッフ_休職中_契約時間を保持したまま実効稼働時間と常勤換算はゼロになる() -> (
    None
):
    # Arrange: 週40時間契約だが育児休業中のスタッフ
    staff_on_leave = _create_staff(
        status=StaffStatus.ON_LEAVE,
        leave_reason=LeaveReason.CHILDCARE,
        weekly_contract_hours=WeeklyContractHours(Decimal("40.0")),
    )

    # Act & Assert: 契約時間自体は保持されているが、実効値は0になる
    assert staff_on_leave.weekly_contract_hours is not None
    assert staff_on_leave.weekly_contract_hours.value == Decimal("40.0")
    assert staff_on_leave.effective_weekly_hours == Decimal("0.0")
    assert staff_on_leave.effective_full_time_equivalent() == Decimal("0.00")
    assert staff_on_leave.effective_is_full_time() is False


def test_スタッフ_退職済または時間未設定_実効稼働時間と常勤換算はゼロになる() -> None:
    # Arrange: 退職済み
    retired_staff = _create_staff(
        status=StaffStatus.RETIRED,
        weekly_contract_hours=WeeklyContractHours(Decimal("40.0")),
    )
    # Arrange: 週契約時間未設定（None）
    unspecified_staff = _create_staff(
        status=StaffStatus.ACTIVE,
        weekly_contract_hours=None,
    )

    # Act & Assert
    assert retired_staff.effective_weekly_hours == Decimal("0.0")
    assert retired_staff.effective_full_time_equivalent() == Decimal("0.00")
    assert retired_staff.effective_is_full_time() is False

    assert unspecified_staff.effective_weekly_hours == Decimal("0.0")
    assert unspecified_staff.effective_full_time_equivalent() == Decimal("0.00")
    assert unspecified_staff.effective_is_full_time() is False
