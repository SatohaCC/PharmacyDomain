"""コンテキストごとのユースケース束をオンデマンドで生成・提供するレジストリ。"""

from __future__ import annotations

from typing import cast

from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.corporate.corporate_access import CorporateAccessService
from app.infrastructure.di.bundles import (
    CorporateUseCases,
    CoverageUseCases,
    DispensingUseCases,
    MedicationHistoryUseCases,
    MedicineCatalogUseCases,
    PatientUseCases,
    PrescriptionUseCases,
    ReceptionUseCases,
    StaffUseCases,
    StoreUseCases,
    build_corporate_use_cases,
    build_coverage_use_cases,
    build_dispensing_use_cases,
    build_medication_history_use_cases,
    build_medicine_catalog_use_cases,
    build_patient_use_cases,
    build_prescription_use_cases,
    build_reception_use_cases,
    build_staff_use_cases,
    build_store_use_cases,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.postgres.repositories import PostgresRepositorySet


class PostgresUseCaseRegistry:
    """コンテキストごとのユースケース束をオンデマンドで生成するレジストリ。

    ここに並ぶ束の合計が、PostgreSQL 経路から実行できる操作のすべてになる。
    プロパティアクセス時に初めて該当コンテキストのユースケース束を組み立てるため、
    リクエストごとに不要なユースケースを一括インスタンス化しない。
    """

    def __init__(
        self,
        repositories: PostgresRepositorySet,
        corporate_access: CorporateAccessService,
        *,
        authorization: AuthorizationService,
        clock: Clock,
        unit_of_work: PostgresUnitOfWork,
    ) -> None:
        self._repositories = repositories
        self._corporate_access = corporate_access
        self._authorization = authorization
        self._clock = clock
        self._unit_of_work = unit_of_work
        self._cache: dict[str, object] = {}

    @property
    def corporate(self) -> CorporateUseCases:
        if "corporate" not in self._cache:
            self._cache["corporate"] = build_corporate_use_cases(
                self._repositories, self._corporate_access
            )
        return cast(CorporateUseCases, self._cache["corporate"])

    @property
    def store(self) -> StoreUseCases:
        if "store" not in self._cache:
            self._cache["store"] = build_store_use_cases(
                self._repositories, self._corporate_access
            )
        return cast(StoreUseCases, self._cache["store"])

    @property
    def staff(self) -> StaffUseCases:
        if "staff" not in self._cache:
            self._cache["staff"] = build_staff_use_cases(
                self._repositories, self._corporate_access, self._clock
            )
        return cast(StaffUseCases, self._cache["staff"])

    @property
    def patient(self) -> PatientUseCases:
        if "patient" not in self._cache:
            self._cache["patient"] = build_patient_use_cases(
                self._repositories, self._corporate_access
            )
        return cast(PatientUseCases, self._cache["patient"])

    @property
    def coverage(self) -> CoverageUseCases:
        if "coverage" not in self._cache:
            self._cache["coverage"] = build_coverage_use_cases(
                self._repositories, self._corporate_access
            )
        return cast(CoverageUseCases, self._cache["coverage"])

    @property
    def reception(self) -> ReceptionUseCases:
        if "reception" not in self._cache:
            self._cache["reception"] = build_reception_use_cases(
                self._repositories, self._corporate_access, self._clock
            )
        return cast(ReceptionUseCases, self._cache["reception"])

    @property
    def prescription(self) -> PrescriptionUseCases:
        if "prescription" not in self._cache:
            self._cache["prescription"] = build_prescription_use_cases(
                self._repositories, self._corporate_access, self._clock
            )
        return cast(PrescriptionUseCases, self._cache["prescription"])

    @property
    def dispensing(self) -> DispensingUseCases:
        if "dispensing" not in self._cache:
            self._cache["dispensing"] = build_dispensing_use_cases(
                self._repositories,
                self._corporate_access,
                self._clock,
                self._unit_of_work,
            )
        return cast(DispensingUseCases, self._cache["dispensing"])

    @property
    def medication_history(self) -> MedicationHistoryUseCases:
        if "medication_history" not in self._cache:
            self._cache["medication_history"] = build_medication_history_use_cases(
                self._repositories,
                self._corporate_access,
                self._clock,
                self._unit_of_work,
            )
        return cast(MedicationHistoryUseCases, self._cache["medication_history"])

    @property
    def medicine_catalog(self) -> MedicineCatalogUseCases:
        if "medicine_catalog" not in self._cache:
            self._cache["medicine_catalog"] = build_medicine_catalog_use_cases(
                self._repositories, self._authorization
            )
        return cast(MedicineCatalogUseCases, self._cache["medicine_catalog"])


# リフレクション検査（test_composition / test_route_coverage）のために型ヒントを明示登録する。
PostgresUseCaseRegistry.__annotations__ = {
    "corporate": CorporateUseCases,
    "store": StoreUseCases,
    "staff": StaffUseCases,
    "patient": PatientUseCases,
    "coverage": CoverageUseCases,
    "reception": ReceptionUseCases,
    "prescription": PrescriptionUseCases,
    "dispensing": DispensingUseCases,
    "medication_history": MedicationHistoryUseCases,
    "medicine_catalog": MedicineCatalogUseCases,
}

__all__ = ["PostgresUseCaseRegistry"]
