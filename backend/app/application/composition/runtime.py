"""Applicationのruntimeを定義する。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from app.application.access_control.boundary_models import (
    ActorContext,
    ResolvedActorContext,
)
from app.application.access_control.policies import AuthorizationService
from app.application.composition.errors import execution_scope
from app.application.composition.registry import (
    CareEventUseCases,
    CorporateUseCases,
    CoverageUseCases,
    DispensingUseCases,
    IdentityUseCases,
    IntegrationUseCases,
    MedicationHistoryUseCases,
    MedicineCatalogUseCases,
    PatientUseCases,
    PrescriptionUseCases,
    ReceptionUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.application.identity.boundary_models import VerifiedSubject
from app.application.identity.commands.dtos.identity_views import AccountDto


class UseCaseRegistry(Protocol):
    """リクエスト内で利用できるユースケース束。"""

    @property
    def corporate(self) -> CorporateUseCases:
        """corporateの操作を提供する。"""
        ...

    @property
    def identity(self) -> IdentityUseCases:
        """identityの操作を提供する。"""
        ...

    @property
    def store(self) -> StoreUseCases:
        """storeの操作を提供する。"""
        ...

    @property
    def staff(self) -> StaffUseCases:
        """staffの操作を提供する。"""
        ...

    @property
    def patient(self) -> PatientUseCases:
        """patientの操作を提供する。"""
        ...

    @property
    def coverage(self) -> CoverageUseCases:
        """coverageの操作を提供する。"""
        ...

    @property
    def reception(self) -> ReceptionUseCases:
        """receptionの操作を提供する。"""
        ...

    @property
    def prescription(self) -> PrescriptionUseCases:
        """prescriptionの操作を提供する。"""
        ...

    @property
    def dispensing(self) -> DispensingUseCases:
        """dispensingの操作を提供する。"""
        ...

    @property
    def medication_history(self) -> MedicationHistoryUseCases:
        """medication_historyの操作を提供する。"""
        ...

    @property
    def care_event(self) -> CareEventUseCases:
        """care_eventの操作を提供する。"""
        ...

    @property
    def medicine_catalog(self) -> MedicineCatalogUseCases:
        """medicine_catalogの操作を提供する。"""
        ...

    @property
    def integration(self) -> IntegrationUseCases:
        """integrationの操作を提供する。"""
        ...


class RequestScope(Protocol):
    """同じトランザクションで動作するユースケースを公開する。"""

    @property
    def use_cases(self) -> UseCaseRegistry:
        """この実行文脈の操作を返す。"""
        ...


class CompositionRoot(Protocol):
    """本人解決、実行文脈の開始、起動資源の終了を提供する。"""

    def request_scope(
        self, *, authorization: AuthorizationService
    ) -> AbstractAsyncContextManager[RequestScope]:
        """リクエストごとの独立した実行文脈を開く。"""
        ...

    async def resolve_identity(self, subject: VerifiedSubject) -> ResolvedActorContext:
        """外部主体から信頼済みの内部操作者を解決する。"""
        ...

    async def accept_invitation(
        self, subject: VerifiedSubject, secret: str
    ) -> AccountDto:
        """通常の認可文脈を作る前に招待を受諾する。"""
        ...

    async def dispose(self) -> None:
        """起動時に取得した資源を解放する。"""
        ...


@asynccontextmanager
async def authorized_request_scope(
    root: CompositionRoot, actor: ActorContext
) -> AsyncIterator[RequestScope]:
    """認証済みの操作者から認可方針を作り、業務実行中の例外を公開境界へ変換する。"""
    async with execution_scope(
        root.request_scope(authorization=AuthorizationService(actor))
    ) as scope:
        yield scope
