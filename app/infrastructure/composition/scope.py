"""1リクエスト分のトランザクションとユースケース一式。"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Self

from app.application.access_control.policy import AuthorizationService
from app.application.common.clock import Clock
from app.application.corporate.corporate_access import CorporateAccessService
from app.infrastructure.composition.corporate import (
    CorporateUseCases,
    build_corporate_use_cases,
)
from app.infrastructure.composition.coverage import (
    CoverageUseCases,
    build_coverage_use_cases,
)
from app.infrastructure.composition.dispensing import (
    DispensingUseCases,
    build_dispensing_use_cases,
)
from app.infrastructure.composition.medication_history import (
    MedicationHistoryUseCases,
    build_medication_history_use_cases,
)
from app.infrastructure.composition.medicine_catalog import (
    MedicineCatalogUseCases,
    build_medicine_catalog_use_cases,
)
from app.infrastructure.composition.patient import (
    PatientUseCases,
    build_patient_use_cases,
)
from app.infrastructure.composition.prescription import (
    PrescriptionUseCases,
    build_prescription_use_cases,
)
from app.infrastructure.composition.reception import (
    ReceptionUseCases,
    build_reception_use_cases,
)
from app.infrastructure.composition.repositories import PostgresRepositorySet
from app.infrastructure.composition.staff import StaffUseCases, build_staff_use_cases
from app.infrastructure.composition.store import StoreUseCases, build_store_use_cases
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork


@dataclass(frozen=True, slots=True)
class PostgresUseCaseRegistry:
    """コンテキストごとのユースケース束。

    ここに並ぶ束の合計が、PostgreSQL 経路から実行できる操作のすべてになる。
    ``tests/infrastructure/test_composition_completeness.py`` が
    ``app/application`` に定義された全ユースケースとの一致を検査するので、
    ユースケースを足して束へ入れ忘れると pytest が落ちる。
    """

    corporate: CorporateUseCases
    store: StoreUseCases
    staff: StaffUseCases
    patient: PatientUseCases
    coverage: CoverageUseCases
    reception: ReceptionUseCases
    prescription: PrescriptionUseCases
    dispensing: DispensingUseCases
    medication_history: MedicationHistoryUseCases
    medicine_catalog: MedicineCatalogUseCases


class PostgresRequestScope:
    """1リクエスト（=1トランザクション）分の実行文脈。

    **トランザクションの開始・確定はここ1箇所にある。** 複数集約を書き込む
    ユースケースには同じ UnitOfWork を必須依存として渡すが、ユースケース自身は
    境界を開きも閉じもしない。実行時に開始済みであることだけを検証する。

    書き込みの取りこぼしも構造で防いでいる。``PostgresUnitOfWork`` はコンテキスト
    の外でセッションを渡さないので、スコープを開かずに Repository を呼ぶと
    ``RuntimeError`` になる。「境界を張り忘れたまま保存が成功する」経路は無い。

    ``AsyncSession`` は並行実行安全ではないため、このインスタンスは
    リクエストをまたいで使い回さない。
    """

    def __init__(
        self,
        unit_of_work: PostgresUnitOfWork,
        *,
        authorization: AuthorizationService,
        clock: Clock,
    ) -> None:
        self._unit_of_work = unit_of_work
        repositories = PostgresRepositorySet.create(unit_of_work)
        corporate_access = CorporateAccessService(repositories.corporate, authorization)
        self._repositories = repositories
        self._use_cases = PostgresUseCaseRegistry(
            corporate=build_corporate_use_cases(repositories, corporate_access),
            store=build_store_use_cases(repositories, corporate_access),
            staff=build_staff_use_cases(repositories, corporate_access, clock),
            patient=build_patient_use_cases(repositories, corporate_access),
            coverage=build_coverage_use_cases(repositories, corporate_access),
            reception=build_reception_use_cases(repositories, corporate_access, clock),
            prescription=build_prescription_use_cases(
                repositories, corporate_access, clock
            ),
            dispensing=build_dispensing_use_cases(
                repositories, corporate_access, clock, unit_of_work
            ),
            medication_history=build_medication_history_use_cases(
                repositories, corporate_access, clock, unit_of_work
            ),
            medicine_catalog=build_medicine_catalog_use_cases(
                repositories, authorization
            ),
        )

    @property
    def use_cases(self) -> PostgresUseCaseRegistry:
        """このスコープで実行できるユースケース一式を返す。"""
        return self._use_cases

    @property
    def repositories(self) -> PostgresRepositorySet:
        """このスコープの Repository 一式を返す。"""
        return self._repositories

    async def __aenter__(self) -> Self:
        """トランザクションを開始する。"""
        await self._unit_of_work.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """例外が無ければコミットし、あれば破棄して閉じる。

        コミットを呼び出し側の作法に委ねない。委ねると、``commit()`` を書き忘れた
        経路が「例外は出ないがデータが消える」振る舞いになる。コミット自体が
        失敗した場合も、``finally`` で Unit of Work を閉じてから例外を伝える。
        """
        try:
            if exc_type is None:
                await self._unit_of_work.commit()
        finally:
            await self._unit_of_work.__aexit__(exc_type, exc_value, traceback)
