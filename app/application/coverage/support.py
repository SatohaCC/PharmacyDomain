"""Coverageユースケース間で共有する処理。"""

from __future__ import annotations

from datetime import date

from app.application.coverage.exceptions import PatientCoverageNotFoundError
from app.base.application.support import to_optional_text
from app.base.domain.exceptions import DomainValidationError
from app.domain.corporate.primitives import CorporateId
from app.domain.coverage import (
    CoverageActivatedOn,
    CoverageActivation,
    CoverageBenefitRatio,
    CoverageBranchNumber,
    CoverageCode,
    CoverageInsuredType,
    CoveragePeriod,
    CoveragePriority,
    CoverageSymbol,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    InsuranceCoverageDetails,
    InsurerNumber,
    PatientCoverage,
    PublicExpenseCoverageDetails,
    PublicPayerNumber,
    PublicRecipientNumber,
)
from app.domain.coverage.primitives import PatientCoverageId
from app.domain.coverage.repository import PatientCoverageRepository

__all__ = [
    "build_activation",
    "build_coverage_period",
    "build_insurance_details",
    "build_priority",
    "build_public_expense_details",
    "load_coverage_or_raise",
    "parse_coverage_type",
    "parse_insured_type",
    "required_text",
    "to_optional_text",
]


def build_activation(*, activated_on: date) -> CoverageActivation:
    """患者資格台帳行の有効化区間を構成する。"""
    return CoverageActivation(activated_on=CoverageActivatedOn(activated_on))


def required_text(raw: str | None, field_name: str) -> str:
    """必須文字列を正規化し、未入力ならドメイン例外を送出する。"""
    value = to_optional_text(raw)
    if value is None:
        raise DomainValidationError(f"{field_name}は必須です。")
    return value


def parse_coverage_type(raw: str) -> CoverageType:
    """入力文字列を患者資格種別へ変換する。"""
    try:
        return CoverageType(raw)
    except ValueError as exc:
        raise DomainValidationError("患者資格種別が不正です。") from exc


def parse_insured_type(raw: str | None) -> CoverageInsuredType:
    """入力文字列を本人・家族区分へ変換する。"""
    value = required_text(raw, "本人・家族区分")
    try:
        return CoverageInsuredType(value)
    except ValueError as exc:
        raise DomainValidationError("本人・家族区分が不正です。") from exc


def build_coverage_period(
    *,
    valid_from: date,
    valid_to: date | None,
) -> CoveragePeriod:
    """適用期間を構成する。"""
    return CoveragePeriod(
        valid_from=CoverageValidFrom(valid_from),
        valid_to=CoverageValidTo(valid_to) if valid_to is not None else None,
    )


def build_insurance_details(
    *,
    insurer_number: str | None,
    insured_symbol: str | None,
    insured_number: str | None,
    branch_number: str | None,
    insured_type: str | None,
    benefit_ratio: int | None,
) -> InsuranceCoverageDetails:
    """保険資格の制度別詳細を構成する。"""
    if benefit_ratio is None:
        raise DomainValidationError("給付割合は必須です。")
    normalized_branch = to_optional_text(branch_number)
    return InsuranceCoverageDetails(
        insurer_number=InsurerNumber(required_text(insurer_number, "保険者番号")),
        insured_symbol=CoverageSymbol(required_text(insured_symbol, "被保険者記号")),
        insured_number=CoverageCode(required_text(insured_number, "被保険者番号")),
        branch_number=(
            CoverageBranchNumber(normalized_branch)
            if normalized_branch is not None
            else None
        ),
        insured_type=parse_insured_type(insured_type),
        benefit_ratio=CoverageBenefitRatio(benefit_ratio),
    )


def build_public_expense_details(
    *,
    payer_number: str | None,
    recipient_number: str | None,
) -> PublicExpenseCoverageDetails:
    """公費負担資格の制度別詳細を構成する。"""
    return PublicExpenseCoverageDetails(
        payer_number=PublicPayerNumber(required_text(payer_number, "公費負担者番号")),
        recipient_number=PublicRecipientNumber(
            required_text(recipient_number, "公費受給者番号")
        ),
    )


def build_priority(raw: int) -> CoveragePriority:
    """優先順位を値オブジェクトへ変換する。"""
    return CoveragePriority(raw)


async def load_coverage_or_raise(
    repository: PatientCoverageRepository,
    *,
    corporate_id: CorporateId,
    coverage_id: PatientCoverageId,
) -> PatientCoverage:
    """指定法人の患者資格を取得し、存在しなければ404相当を送出する。"""
    coverage = await repository.get(
        corporate_id=corporate_id,
        coverage_id=coverage_id,
    )
    if coverage is None:
        raise PatientCoverageNotFoundError()
    return coverage
