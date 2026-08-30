"""1リクエスト分の実行文脈を組み立てるFastAPI依存。

**トランザクション境界を開くのはここ1箇所だけである。** ルータは開いた文脈から
ユースケース束を受け取るだけで、``commit`` も ``rollback`` も呼ばない。
確定と破棄は ``PostgresRequestScope`` が担う。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.access_control import ActorContext, AuthorizationService
from app.infrastructure.composition import (
    CorporateUseCases,
    CoverageUseCases,
    DispensingUseCases,
    MedicationHistoryUseCases,
    MedicineCatalogUseCases,
    PatientUseCases,
    PostgresCompositionRoot,
    PostgresRequestScope,
    PrescriptionUseCases,
    ReceptionUseCases,
    StaffUseCases,
    StoreUseCases,
)
from app.presentational.authentication import ActorContextProvider

#: アプリケーション状態を置く ``app.state`` の属性名。
STATE_ATTRIBUTE: Final = "pharmacy_state"

#: OpenAPI へ載せる認証方式。``/docs`` の Authorize から資格情報を入れられる。
#:
#: ``auto_error=False`` にして、ヘッダが無いときの応答をFastAPI任せにしない。
#: 既定では未認証が403（権限不足）として返るが、主体がまだ決まっていない状態は
#: 401であり、しかも本文がこのAPIの共通形にならない。
bearer_scheme = HTTPBearer(
    auto_error=False,
    description="認証基盤が発行したアクセストークン。",
)


@dataclass(frozen=True, slots=True)
class PresentationState:
    """プロセスの寿命を持つ依存。

    ``composition_root`` はDBエンジンを抱えるためlifespanでしか作れないが、
    ``actor_provider`` はアプリ生成時に決まる。分けて持たせることで、DBへ届く
    前に認証を落とせる（未認証のリクエストがDB接続を1本消費しない）。
    """

    actor_provider: ActorContextProvider
    composition_root: PostgresCompositionRoot | None = None


def get_state(request: Request) -> PresentationState:
    """アプリケーション状態を取り出す。"""
    state = getattr(request.app.state, STATE_ATTRIBUTE, None)
    if not isinstance(state, PresentationState):
        raise RuntimeError(
            "アプリケーション状態が初期化されていません。"
            "app.presentational.create_app() で生成してください。"
        )
    return state


def get_composition_root(
    state: Annotated[PresentationState, Depends(get_state)],
) -> PostgresCompositionRoot:
    """起動時に組み立てた Composition Root を取り出す。"""
    if state.composition_root is None:
        raise RuntimeError(
            "Composition Root が未初期化です。lifespanを開始せずに"
            "業務エンドポイントを呼び出しています。"
        )
    return state.composition_root


async def get_actor_context(
    state: Annotated[PresentationState, Depends(get_state)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> ActorContext:
    """Bearerトークンを認証基盤へ渡して操作主体を決める。

    トークンの中身をここで解釈しない。渡すのは資格情報だけで、ロールと所属法人を
    決めるのは認証基盤の実装である。``Depends`` に ``HTTPBearer`` を置いているので、
    この依存を使うルートには OpenAPI の ``security`` が自動で付く。
    """
    return await state.actor_provider.authenticate(
        credentials.credentials if credentials is not None else None
    )


async def get_request_scope(
    root: Annotated[PostgresCompositionRoot, Depends(get_composition_root)],
    actor: Annotated[ActorContext, Depends(get_actor_context)],
) -> AsyncIterator[PostgresRequestScope]:
    """リクエスト1件分のトランザクションを開き、終了時に確定または破棄する。

    ルータで例外が起きた場合はこの ``async with`` へ伝播し、``PostgresRequestScope``
    が破棄する。正常終了時だけ確定する。
    """
    async with root.request_scope(authorization=AuthorizationService(actor)) as scope:
        yield scope


#: 開いたスコープ。コンテキストごとの束はここから取り出す。
_Scope = Annotated[PostgresRequestScope, Depends(get_request_scope)]


def get_corporate_use_cases(scope: _Scope) -> CorporateUseCases:
    """法人コンテキストのユースケース束を返す。"""
    return scope.use_cases.corporate


def get_store_use_cases(scope: _Scope) -> StoreUseCases:
    """店舗コンテキストのユースケース束を返す。"""
    return scope.use_cases.store


def get_staff_use_cases(scope: _Scope) -> StaffUseCases:
    """スタッフコンテキストのユースケース束を返す。"""
    return scope.use_cases.staff


def get_patient_use_cases(scope: _Scope) -> PatientUseCases:
    """患者コンテキストのユースケース束を返す。"""
    return scope.use_cases.patient


def get_coverage_use_cases(scope: _Scope) -> CoverageUseCases:
    """資格台帳コンテキストのユースケース束を返す。"""
    return scope.use_cases.coverage


def get_reception_use_cases(scope: _Scope) -> ReceptionUseCases:
    """受付コンテキストのユースケース束を返す。"""
    return scope.use_cases.reception


def get_prescription_use_cases(scope: _Scope) -> PrescriptionUseCases:
    """処方箋コンテキストのユースケース束を返す。"""
    return scope.use_cases.prescription


def get_dispensing_use_cases(scope: _Scope) -> DispensingUseCases:
    """調剤コンテキストのユースケース束を返す。"""
    return scope.use_cases.dispensing


def get_medication_history_use_cases(scope: _Scope) -> MedicationHistoryUseCases:
    """薬歴コンテキストのユースケース束を返す。"""
    return scope.use_cases.medication_history


def get_medicine_catalog_use_cases(scope: _Scope) -> MedicineCatalogUseCases:
    """医薬品マスタコンテキストのユースケース束を返す。"""
    return scope.use_cases.medicine_catalog


#: ルータが受け取る依存の別名。
Actor = Annotated[ActorContext, Depends(get_actor_context)]
CorporateUseCasesDep = Annotated[CorporateUseCases, Depends(get_corporate_use_cases)]
StoreUseCasesDep = Annotated[StoreUseCases, Depends(get_store_use_cases)]
StaffUseCasesDep = Annotated[StaffUseCases, Depends(get_staff_use_cases)]
PatientUseCasesDep = Annotated[PatientUseCases, Depends(get_patient_use_cases)]
CoverageUseCasesDep = Annotated[CoverageUseCases, Depends(get_coverage_use_cases)]
ReceptionUseCasesDep = Annotated[ReceptionUseCases, Depends(get_reception_use_cases)]
PrescriptionUseCasesDep = Annotated[
    PrescriptionUseCases, Depends(get_prescription_use_cases)
]
DispensingUseCasesDep = Annotated[DispensingUseCases, Depends(get_dispensing_use_cases)]
MedicationHistoryUseCasesDep = Annotated[
    MedicationHistoryUseCases, Depends(get_medication_history_use_cases)
]
MedicineCatalogUseCasesDep = Annotated[
    MedicineCatalogUseCases, Depends(get_medicine_catalog_use_cases)
]


__all__ = [
    "STATE_ATTRIBUTE",
    "Actor",
    "CorporateUseCasesDep",
    "CoverageUseCasesDep",
    "DispensingUseCasesDep",
    "MedicationHistoryUseCasesDep",
    "MedicineCatalogUseCasesDep",
    "PatientUseCasesDep",
    "PrescriptionUseCasesDep",
    "PresentationState",
    "ReceptionUseCasesDep",
    "StaffUseCasesDep",
    "StoreUseCasesDep",
    "bearer_scheme",
    "get_actor_context",
    "get_composition_root",
    "get_corporate_use_cases",
    "get_coverage_use_cases",
    "get_dispensing_use_cases",
    "get_medication_history_use_cases",
    "get_medicine_catalog_use_cases",
    "get_patient_use_cases",
    "get_prescription_use_cases",
    "get_reception_use_cases",
    "get_request_scope",
    "get_staff_use_cases",
    "get_state",
    "get_store_use_cases",
]
