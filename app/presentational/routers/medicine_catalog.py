"""医薬品マスタコンテキストのHTTPルート。

**このルータだけ法人IDをパスに持たない。** 薬価基準は国が定める参照データで、
法人ごとに内容が違わない。法人配下に置くと、改定のたびに全テナント分を更新する
羽目になる。取り込みはベンダーシステム管理者専用だが、その判定はユースケースが
``Permission`` で行う。

参照は必ず時点で引く。麻薬指定も経過措置期限も改定で変わるため、「今」で引くと
過去の処方を新しいマスタで判定してしまう。``as_of`` は必須にしてある。
"""

from __future__ import annotations

from datetime import date
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.application.medicine_catalog import (
    GetEffectiveMedicineQuery,
    MedicineDto,
    RegisterMedicineCommand,
)
from app.presentational.dependencies import (
    MedicineCatalogUseCasesDep,
    get_actor_context,
)
from app.presentational.errors import error_responses
from app.presentational.schemas import RequestModel

router = APIRouter(
    prefix="/medicines",
    tags=["medicine_catalog"],
    dependencies=[Depends(get_actor_context)],
    responses=error_responses(
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.UNPROCESSABLE_CONTENT,
    ),
)


class RegisterMedicineRequest(RequestModel):
    """医薬品の取り込みの入力。収載期間は終了日を含む閉区間として扱う。"""

    code_type: str
    code: str
    name: str
    unit: str
    dosage_form: str
    listed_on: date
    catalog_version: date
    withdrawn_on: date | None = None
    narcotic_category: str = "none"
    generic_category: str = "other"
    has_dosage_limit: bool = False
    is_analgesic_antiinflammatory: bool = False
    is_dermatological: bool = False


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    response_model=MedicineDto,
    responses=error_responses(HTTPStatus.CONFLICT),
)
async def register_medicine(
    body: RegisterMedicineRequest,
    use_cases: MedicineCatalogUseCasesDep,
) -> MedicineDto:
    """医薬品マスタへ1件取り込む（ベンダーシステム管理者専用）。"""
    return await use_cases.register.execute(
        RegisterMedicineCommand(
            code_type=body.code_type,
            code=body.code,
            name=body.name,
            unit=body.unit,
            dosage_form=body.dosage_form,
            listed_on=body.listed_on,
            catalog_version=body.catalog_version,
            withdrawn_on=body.withdrawn_on,
            narcotic_category=body.narcotic_category,
            generic_category=body.generic_category,
            has_dosage_limit=body.has_dosage_limit,
            is_analgesic_antiinflammatory=body.is_analgesic_antiinflammatory,
            is_dermatological=body.is_dermatological,
        )
    )


@router.get(
    "/{code_type}/{code}",
    response_model=MedicineDto,
    responses=error_responses(HTTPStatus.NOT_FOUND),
)
async def get_effective_medicine(
    code_type: str,
    code: str,
    use_cases: MedicineCatalogUseCasesDep,
    as_of: Annotated[
        date,
        Query(description="収載期間の判定に使う時点。処方箋の判定では交付日を渡す。"),
    ],
) -> MedicineDto:
    """指定時点で有効な医薬品を取得する。"""
    return await use_cases.get_effective.execute(
        GetEffectiveMedicineQuery(code_type=code_type, code=code, as_of=as_of)
    )


__all__ = ["router"]
