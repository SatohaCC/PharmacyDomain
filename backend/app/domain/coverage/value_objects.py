"""coverageの複合値と参照スナップショット。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, Self

from app.domain.corporate.identifiers import CorporateId
from app.domain.coverage.exceptions import (
    CoverageCombinationError,
    CoverageCombinationInvalidError,
    CoverageSelectionInvalidError,
)
from app.domain.coverage.identifiers import PatientCoverageId
from app.domain.coverage.primitives import (
    CoverageActivatedOn,
    CoverageBenefitRatio,
    CoverageBranchNumber,
    CoverageCode,
    CoverageDeactivatedOn,
    CoverageInsuredType,
    CoveragePriority,
    CoverageSymbol,
    CoverageType,
    CoverageValidFrom,
    CoverageValidTo,
    InsurerNumber,
    PriorityViolation,
    PublicPayerNumber,
    PublicRecipientNumber,
    find_priority_violation,
)
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.value_object import ValueObject
from app.domain.patient.identifiers import PatientId

#: 公費は第一公費から第四公費までを同時に適用できる。
MAXIMUM_PUBLIC_EXPENSE_COUNT = 4


#: 順位規則の違反種別に対応する日本語メッセージ。規則本体はCoverageの
#: primitivesに1つだけ置き、各検証箇所で同じ文言を使う。
PUBLIC_EXPENSE_PRIORITY_MESSAGES: Mapping[PriorityViolation, str] = {
    PriorityViolation.EXCEEDS_MAXIMUM: "公費は第四公費まで指定できます。",
    PriorityViolation.DUPLICATED: "公費の適用順位は重複して指定できません。",
    PriorityViolation.NOT_CONSECUTIVE: (
        "公費の適用順位は第一公費から連続して指定してください。"
    ),
}


@dataclass(frozen=True, kw_only=True)
class SelectedInsuranceCoverage(ValueObject):
    """処方受付時に選択・適用された健康保険資格（主保険）の控えデータ。"""

    source_coverage_id: PatientCoverageId
    corporate_id: CorporateId
    patient_id: PatientId
    applied_on: date
    coverage_type: CoverageType
    priority: CoveragePriority
    details: InsuranceCoverageDetails

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "corporate_id": "法人ID",
        "patient_id": "患者ID",
        "applied_on": "適用日",
        "coverage_type": "資格種別",
        "priority": "適用順位",
        "details": "医療保険詳細",
    }

    def validate(self) -> None:
        """医療保険枠の種別と順位を検証する。"""
        if self.coverage_type is not CoverageType.INSURANCE:
            raise CoverageCombinationError("医療保険枠には医療保険資格が必要です。")
        if self.priority.value != 1:
            raise CoverageCombinationError(
                "医療保険の適用順位は1である必要があります。"
            )


@dataclass(frozen=True, kw_only=True)
class SelectedPublicExpenseCoverage(ValueObject):
    """処方受付時に選択・適用された公費負担医療（第一〜第四公費）の控えデータ。"""

    source_coverage_id: PatientCoverageId
    corporate_id: CorporateId
    patient_id: PatientId
    applied_on: date
    coverage_type: CoverageType
    priority: CoveragePriority
    details: PublicExpenseCoverageDetails

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "corporate_id": "法人ID",
        "patient_id": "患者ID",
        "applied_on": "適用日",
        "coverage_type": "資格種別",
        "priority": "適用順位",
        "details": "公費詳細",
    }

    def validate(self) -> None:
        """公費枠へ公費資格だけが入ることを検証する。"""
        if self.coverage_type is not CoverageType.PUBLIC_EXPENSE:
            raise CoverageCombinationError("公費枠には公費資格が必要です。")


@dataclass(frozen=True, kw_only=True)
class CoverageCombination(ValueObject):
    """処方受付時に確定した健康保険（主保険 0〜1件）と公費負担医療（第一〜第四公費）の組み合わせ。"""

    insurance: SelectedInsuranceCoverage | None = None
    public_expenses: tuple[SelectedPublicExpenseCoverage, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurance": "医療保険資格",
        "public_expenses": "公費資格",
    }

    def _normalize_fields(self) -> None:
        """公費を適用順位順へ正規化する。"""
        if not isinstance(self.public_expenses, tuple) or not all(
            isinstance(item, SelectedPublicExpenseCoverage)
            for item in self.public_expenses
        ):
            return
        ordered = tuple(
            sorted(self.public_expenses, key=lambda item: item.priority.value)
        )
        object.__setattr__(self, "public_expenses", ordered)

    def validate(self) -> None:
        """件数・順位・テナント・患者・適用日の一貫性を検証する。"""
        selected = self._all_selected()
        if not selected:
            raise CoverageCombinationError("適用資格を1件以上指定してください。")

        violation = find_priority_violation(
            [item.priority.value for item in self.public_expenses],
            maximum=MAXIMUM_PUBLIC_EXPENSE_COUNT,
        )
        if violation is not None:
            raise CoverageCombinationError(PUBLIC_EXPENSE_PRIORITY_MESSAGES[violation])

        first = selected[0]
        if any(item.corporate_id != first.corporate_id for item in selected[1:]):
            raise CoverageCombinationError("異なる法人の資格は組み合わせられません。")
        if any(item.patient_id != first.patient_id for item in selected[1:]):
            raise CoverageCombinationError("異なる患者の資格は組み合わせられません。")
        if any(item.applied_on != first.applied_on for item in selected[1:]):
            raise CoverageCombinationError("異なる適用日の資格は組み合わせられません。")

    def _all_selected(
        self,
    ) -> tuple[SelectedInsuranceCoverage | SelectedPublicExpenseCoverage, ...]:
        """医療保険を先頭、公費を順位順にした選択列を返す。"""
        insurance = (self.insurance,) if self.insurance is not None else ()
        return insurance + self.public_expenses


@dataclass(frozen=True, kw_only=True)
class SelectedInsuranceSource(ValueObject):
    """医療保険枠。選択元の患者資格IDと適用時点の固定値を1対1で束ねる。"""

    source_coverage_id: PatientCoverageId
    values: InsuranceCoverageSnapshot

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "values": "医療保険スナップショット",
    }


@dataclass(frozen=True, kw_only=True)
class SelectedPublicExpenseSource(ValueObject):
    """公費枠1つ。適用順位は値側が持つので、IDと順位が離れることがない。"""

    source_coverage_id: PatientCoverageId
    values: PublicExpenseCoverageSnapshot

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "source_coverage_id": "選択元患者資格ID",
        "values": "公費スナップショット",
    }

    @property
    def priority(self) -> CoveragePriority:
        """適用順位を値側から返す。"""
        return self.values.priority


@dataclass(frozen=True, kw_only=True)
class CoverageSelection(ValueObject):
    """医療保険枠0〜1個と公費枠0〜4個からなる、適用資格の選択。"""

    insurance: SelectedInsuranceSource | None = None
    public_expenses: tuple[SelectedPublicExpenseSource, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurance": "医療保険枠",
        "public_expenses": "公費枠",
    }

    @classmethod
    def from_combination(cls, combination: CoverageCombination) -> Self:
        """有効性検証済みの組み合わせを、保存可能な選択へ変換する。"""
        insurance = combination.insurance
        selected_insurance = None
        if insurance is not None:
            details = insurance.details
            if details.insured_type is None or details.benefit_ratio is None:
                raise CoverageCombinationError("適用資格の保険情報が不足しています。")
            selected_insurance = SelectedInsuranceSource(
                source_coverage_id=insurance.source_coverage_id,
                values=InsuranceCoverageSnapshot(
                    insurer_number=details.insurer_number,
                    insured_symbol=details.insured_symbol,
                    insured_number=details.insured_number,
                    insured_type=details.insured_type,
                    benefit_ratio=details.benefit_ratio,
                    branch_number=details.branch_number,
                ),
            )
        return cls(
            insurance=selected_insurance,
            public_expenses=tuple(
                SelectedPublicExpenseSource(
                    source_coverage_id=item.source_coverage_id,
                    values=PublicExpenseCoverageSnapshot(
                        priority=item.priority,
                        payer_number=item.details.payer_number,
                        recipient_number=item.details.recipient_number,
                    ),
                )
                for item in combination.public_expenses
            ),
        )

    def _normalize_fields(self) -> None:
        """公費枠を適用順位順へ正規化する。

        順位は値側にあるので、並べ替えてもIDとの対応は動かない。どんな入力順で
        渡しても同一の ``CoverageSelection`` になり、並び順という自由度が消える。
        """
        if not isinstance(self.public_expenses, tuple) or not all(
            isinstance(item, SelectedPublicExpenseSource)
            for item in self.public_expenses
        ):
            return
        ordered = tuple(
            sorted(self.public_expenses, key=lambda item: item.priority.value)
        )
        object.__setattr__(self, "public_expenses", ordered)

    def validate(self) -> None:
        """元資格IDの重複を拒否し、値側の組み合わせ規則も凍結時に走らせる。

        件数一致の検証は不要である。枠の外にIDも値も存在しえないため、
        件数がズレた状態を作る手段が構造的に無い。

        Raises:
            CoverageSelectionInvalidError: 同じ元資格IDを複数の枠へ指定した場合。
            CoverageCombinationInvalidError: 枠が1つも無い、公費が第五以降まで
                ある、公費順位が重複または第一公費から連続していない場合。
                値側の規則なので Coverage の例外をそのまま返す。
        """
        source_ids = self.source_coverage_ids
        if len(source_ids) != len(set(source_ids)):
            raise CoverageSelectionInvalidError(
                "同じ選択元患者資格IDを複数の枠へ指定できません。"
            )
        # 遅延評価にすると「作れてしまうが後で爆発する」ため、構築時に走らせる。
        self._build_snapshot()

    def _build_snapshot(self) -> CoverageSnapshot:
        """枠から適用固定スナップショットを組み立てる。"""
        return CoverageSnapshot(
            insurance=self.insurance.values if self.insurance is not None else None,
            public_expenses=tuple(item.values for item in self.public_expenses),
        )

    @property
    def snapshot(self) -> CoverageSnapshot:
        """適用固定スナップショット。枠構造からの導出値。"""
        return self._build_snapshot()

    @property
    def source_coverage_ids(self) -> tuple[PatientCoverageId, ...]:
        """選択元IDを医療保険、公費順位順で返す。枠構造からの導出値。

        崩れた並びを保持する記憶域が存在しないので、毎回この順で生成される。
        """
        insurance = (
            (self.insurance.source_coverage_id,) if self.insurance is not None else ()
        )
        return insurance + tuple(
            item.source_coverage_id for item in self.public_expenses
        )


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageSnapshot(ValueObject):
    """適用時点の健康保険証情報（保険者番号・記号番号・給付割合等）の控えデータ。

    ``benefit_ratio`` は患者負担額（自己負担割合・給付割合）を決める値であり、
    請求データの整合性を保つ目的そのものなので必須項目です。
    資格台帳の :class:`InsuranceCoverageDetails` と必須性を揃えています。
    """

    insurer_number: InsurerNumber
    insured_symbol: CoverageSymbol
    insured_number: CoverageCode
    insured_type: CoverageInsuredType
    benefit_ratio: CoverageBenefitRatio
    branch_number: CoverageBranchNumber | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurer_number": "保険者番号",
        "insured_symbol": "被保険者記号",
        "insured_number": "被保険者番号",
        "insured_type": "本人・家族区分",
        "benefit_ratio": "給付割合",
        "branch_number": "枝番",
    }


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageSnapshot(ValueObject):
    """適用時点の公費負担医療（第一〜第四公費）の控えデータ。"""

    priority: CoveragePriority
    payer_number: PublicPayerNumber
    recipient_number: PublicRecipientNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "priority": "公費適用順位",
        "payer_number": "公費負担者番号",
        "recipient_number": "公費受給者番号",
    }


@dataclass(frozen=True, kw_only=True)
class CoverageSnapshot(ValueObject):
    """適用時点で固定した健康保険および公費負担医療の組み合わせ控えデータ。"""

    insurance: InsuranceCoverageSnapshot | None = None
    public_expenses: tuple[PublicExpenseCoverageSnapshot, ...] = ()

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurance": "医療保険スナップショット",
        "public_expenses": "公費スナップショット",
    }

    def _normalize_fields(self) -> None:
        """公費スナップショットを順位順へ正規化する。"""
        if not isinstance(self.public_expenses, tuple) or not all(
            isinstance(item, PublicExpenseCoverageSnapshot)
            for item in self.public_expenses
        ):
            return
        public_expenses = self.public_expenses
        ordered = tuple(sorted(public_expenses, key=lambda item: item.priority.value))
        object.__setattr__(self, "public_expenses", ordered)

    def validate(self) -> None:
        """健康保険および公費の指定件数（1件以上必須）と公費の適用順位（第一〜第四公費の連続性）を検証する。"""
        public_expenses = self.public_expenses
        if self.insurance is None and not public_expenses:
            raise CoverageCombinationInvalidError(
                "保険または公費を1件以上指定してください。"
            )

        violation = find_priority_violation(
            [item.priority.value for item in public_expenses],
            maximum=MAXIMUM_PUBLIC_EXPENSE_COUNT,
        )
        if violation is not None:
            raise CoverageCombinationInvalidError(
                PUBLIC_EXPENSE_PRIORITY_MESSAGES[violation]
            )


@dataclass(frozen=True, kw_only=True)
class CoveragePeriod(ValueObject):
    """患者資格の適用期間。終了日なしは現在も有効であることを表す。

    日付型の検証は :class:`CoverageValidFrom` / :class:`CoverageValidTo` が
    :class:`BaseDate` から受け継ぐため、ここでは前後関係だけを検証する。
    """

    valid_from: CoverageValidFrom
    valid_to: CoverageValidTo | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "valid_from": "適用開始日",
        "valid_to": "適用終了日",
    }

    def validate(self) -> None:
        """適用開始日と適用終了日の前後関係を検証する。"""
        if self.valid_to is not None and self.valid_from.value > self.valid_to.value:
            raise DomainValidationError(
                "適用終了日は適用開始日以降で指定してください。"
            )

    def overlaps(self, other: CoveragePeriod) -> bool:
        """この期間と別の期間が1日でも重なるかを返す。"""
        left_ends_before_right_starts = (
            self.valid_to is not None and self.valid_to.value < other.valid_from.value
        )
        right_ends_before_left_starts = (
            other.valid_to is not None and other.valid_to.value < self.valid_from.value
        )
        return not (left_ends_before_right_starts or right_ends_before_left_starts)


@dataclass(frozen=True, kw_only=True)
class InsuranceCoverageDetails(ValueObject):
    """健康保険資格の制度別詳細。"""

    insurer_number: InsurerNumber
    insured_symbol: CoverageSymbol
    insured_number: CoverageCode
    insured_type: CoverageInsuredType | None
    benefit_ratio: CoverageBenefitRatio | None
    branch_number: CoverageBranchNumber | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "insurer_number": "保険者番号",
        "insured_symbol": "被保険者記号",
        "insured_number": "被保険者番号",
        "insured_type": "本人・家族区分",
        "benefit_ratio": "給付割合",
        "branch_number": "枝番",
    }


@dataclass(frozen=True, kw_only=True)
class PublicExpenseCoverageDetails(ValueObject):
    """公費負担資格の制度別詳細。"""

    payer_number: PublicPayerNumber
    recipient_number: PublicRecipientNumber

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "payer_number": "公費負担者番号",
        "recipient_number": "公費受給者番号",
    }


@dataclass(frozen=True, kw_only=True)
class CoverageActivation(ValueObject):
    """患者資格台帳行の半開有効区間 ``[activated_on, deactivated_on)``。"""

    activated_on: CoverageActivatedOn
    deactivated_on: CoverageDeactivatedOn | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "activated_on": "有効化発効日",
        "deactivated_on": "無効化発効日",
    }

    def validate(self) -> None:
        """無効化発効日が有効化発効日より前でないことを検証する。"""
        if (
            self.deactivated_on is not None
            and self.deactivated_on.value < self.activated_on.value
        ):
            raise DomainValidationError(
                "無効化発効日は有効化発効日以降で指定してください。"
            )

    def is_active_on(self, target_date: date) -> bool:
        """指定日が半開有効区間に含まれるかを返す。"""
        if not isinstance(target_date, date) or isinstance(target_date, datetime):
            raise DomainValidationError("判定日は日付型で指定してください。")
        return self.activated_on.value <= target_date and (
            self.deactivated_on is None or target_date < self.deactivated_on.value
        )
