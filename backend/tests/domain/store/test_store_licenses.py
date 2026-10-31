"""店舗許認可（薬局開設許可・麻薬小売業者免許）のドメインモデルテスト。"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.store.primitives import NarcoticsLicenseNumber, PharmacyLicenseNumber
from app.domain.store.value_objects import NarcoticsRetailerLicense, PharmacyLicense


def test_薬局許可期間_終了日が開始日以後なら受け入れる() -> None:
    # Arrange / Act: 開始=終了、開始<終了
    same_day = PharmacyLicense(
        number=PharmacyLicenseNumber("薬-001"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2026, 10, 29),
    )
    long_period = PharmacyLicense(
        number=PharmacyLicenseNumber("薬-002"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2036, 10, 28),
    )

    # Assert
    assert same_day.is_effective_on(date(2026, 10, 29)) is True
    assert long_period.is_effective_on(date(2030, 1, 1)) is True


def test_薬局許可期間_終了日が開始日より前なら拒否する() -> None:
    # Arrange / Act / Assert: 逆転した日付
    with pytest.raises(DomainValidationError) as exc_info:
        PharmacyLicense(
            number=PharmacyLicenseNumber("薬-001"),
            valid_from=date(2026, 10, 29),
            valid_to=date(2026, 10, 28),
        )
    assert "満了日以前" in str(exc_info.value)


def test_麻薬小売業者免許_原本満了日が翌々年末なら受け入れる() -> None:
    # Arrange / Act: 2026-10-29 の翌々年末は 2028-12-31
    license_obj = NarcoticsRetailerLicense(
        number=NarcoticsLicenseNumber("麻-001"),
        valid_from=date(2026, 10, 29),
        valid_to=date(2028, 12, 31),
    )

    # Assert
    assert license_obj.valid_to == date(2028, 12, 31)
    assert license_obj.is_effective_on(date(2026, 10, 29)) is True
    assert license_obj.is_effective_on(date(2028, 12, 31)) is True
    assert license_obj.is_effective_on(date(2026, 10, 28)) is False
    assert license_obj.is_effective_on(date(2029, 1, 1)) is False


def test_麻薬小売業者免許_原本満了日が翌々年末と異なれば拒否する() -> None:
    # Arrange / Act / Assert: 2028-12-30 や 2029-12-31 など不一致の満了日は拒否
    for bad_expiry in [date(2028, 12, 30), date(2029, 12, 31)]:
        with pytest.raises(DomainValidationError):
            NarcoticsRetailerLicense(
                number=NarcoticsLicenseNumber("麻-001"),
                valid_from=date(2026, 10, 29),
                valid_to=bad_expiry,
            )


@pytest.mark.parametrize(
    "valid_from,expected_valid_to",
    [
        (date(2026, 1, 1), date(2028, 12, 31)),
        (date(2026, 12, 31), date(2028, 12, 31)),
        (date(2024, 2, 29), date(2026, 12, 31)),  # 閏日開始
    ],
)
def test_麻薬小売業者免許_年初年末閏日の原本満了日を保持する(
    valid_from: date, expected_valid_to: date
) -> None:
    license_obj = NarcoticsRetailerLicense(
        number=NarcoticsLicenseNumber("麻-001"),
        valid_from=valid_from,
        valid_to=expected_valid_to,
    )
    assert license_obj.valid_to == expected_valid_to


@pytest.mark.parametrize(
    "valid_from,bad_valid_to",
    [
        (date(2026, 1, 1), date(2028, 12, 30)),
        (date(2026, 1, 1), date(2029, 1, 1)),
        (date(2026, 12, 31), date(2028, 12, 30)),
        (date(2026, 12, 31), date(2029, 1, 1)),
        (date(2024, 2, 29), date(2026, 12, 30)),
        (date(2024, 2, 29), date(2027, 1, 1)),
    ],
)
def test_麻薬小売業者免許_年初年末閏日の原本満了日が前後1日なら拒否する(
    valid_from: date, bad_valid_to: date
) -> None:
    with pytest.raises(DomainValidationError):
        NarcoticsRetailerLicense(
            number=NarcoticsLicenseNumber("麻-001"),
            valid_from=valid_from,
            valid_to=bad_valid_to,
        )
