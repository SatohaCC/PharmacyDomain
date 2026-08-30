"""失敗応答の契約（ステータス・本文・OpenAPIへの記載）を1箇所に持つ。

**ステータスの決定はここだけにある。** 各ルータで ``try/except`` を書くと、
同じ例外がエンドポイントごとに違うステータスで返り、クライアントは分岐を
書けなくなる。

対応づけは基底クラスへ広く与え、基底と違う扱いにするものだけを個別に載せる。
どの例外がどの基底を継承しているかは一定ではない（例えば ``StoreNotFoundError``
は ``NotFoundError`` ではなく ``StoreApplicationError`` を継承する）ため、
継承だけに任せると未検出が422で返ってしまう。取りこぼしは
``tests/presentational/test_errors.py`` が全例外クラスを走査して落とす。

**本文の形も1つに揃える。** ドメイン由来の失敗だけでなく、FastAPI の入力検証と
経路解決の失敗も同じ ``ErrorResponse`` へ翻訳する。同じ422で本文の形が2種類
あると、クライアントは422を見ても分岐を書けない。
"""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Final

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.common.exceptions import (
    ApplicationError,
    AuthorizationError,
    NotFoundError,
)
from app.application.coverage.exceptions import (
    CoveragePatientNotFoundError,
    PatientCoverageNotFoundError,
)
from app.application.dispensing.exceptions import (
    DispensingNotFoundError,
    DispensingPrescriptionNotFoundError,
    DispensingStaffNotFoundError,
    DispensingStoreNotFoundError,
)
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
    PatientMedicalProfileNotFoundError,
)
from app.application.medicine_catalog.exceptions import MedicineNotFoundError
from app.application.patient.exceptions import (
    PatientExternalIdentifierNotFoundError,
    PatientNotFoundError,
)
from app.application.prescription.exceptions import (
    PrescriptionCoverageSelectionNotFoundError,
    PrescriptionNotFoundError,
    PrescriptionPatientNotFoundError,
    PrescriptionPharmacistNotFoundError,
    PrescriptionStoreNotFoundError,
)
from app.application.reception.exceptions import (
    ReceptionPatientNotFoundError,
    ReceptionStoreNotFoundError,
)
from app.application.staff.exceptions import (
    StaffNotFoundError as StaffApplicationNotFoundError,
)
from app.application.store.exceptions import StoreNotFoundError
from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.coverage.exceptions import (
    CoverageDeactivationAlreadyFixedError,
    CoveragePeriodConflictError,
)
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.foundation.exceptions import ConcurrentModificationError, DomainError
from app.domain.medication_history.exceptions import (
    ConcurrentMedicationNotFoundError,
    MedicationHistoryAlreadyExistsError,
    MedicationHistoryAlreadyFinalizedError,
    PatientMedicalProfileAlreadyExistsError,
)
from app.domain.medicine_catalog.exceptions import MedicineEffectivePeriodConflictError
from app.domain.patient.exceptions import PatientExternalIdentifierAlreadyExistsError
from app.domain.prescription.exceptions import (
    InquiryAlreadyResolvedError,
    InquiryNotFoundError,
    PrescriptionDocumentNumberAlreadyExistsError,
)
from app.domain.staff.exceptions import (
    AffiliationDateConflictError,
    ConcurrentStoreConflictError,
    StaffCodeAlreadyExistsError,
)
from app.domain.staff.exceptions import StaffNotFoundError as StaffDomainNotFoundError
from app.domain.store.exceptions import (
    InsurancePharmacyNumberAlreadyExistsError,
    StoreCodeAlreadyExistsError,
    StoreNameAlreadyExistsError,
)
from app.presentational.exceptions import AuthenticationError, PresentationError

#: 応答本文へ翻訳できる例外。これ以外は隠さず500として扱う。
TranslatableError = DomainError | ApplicationError | PresentationError


class FieldError(BaseModel):
    """入力検証で弾かれた項目1件。"""

    #: ``body.name`` のように、本文・パス・クエリの位置を点でつないだもの。
    location: str
    message: str


class ErrorResponse(BaseModel):
    """すべての失敗応答が共有する本文。

    成功以外はこの形1つに揃える。``code`` は安定した識別子でクライアントの分岐に
    使い、``message`` は人が読むためのもので分岐に使わせない。``errors`` は入力
    検証のときだけ埋まるが、キー自体は常に存在させる（有無で形が変わると、結局
    2種類の本文を扱うことになる）。
    """

    code: str
    message: str
    errors: list[FieldError] = []


#: 経路解決の失敗に返す日本語メッセージ。既定は英語なので業務の応答と揃わない。
_ROUTING_MESSAGES: Final[Mapping[HTTPStatus, str]] = {
    HTTPStatus.NOT_FOUND: "指定されたリソースが見つかりません。",
    HTTPStatus.METHOD_NOT_ALLOWED: "このパスでは指定されたメソッドを使用できません。",
}

#: OpenAPI に載せるエラー応答の説明。返しうるステータスは全部ここに要る。
_ERROR_DESCRIPTIONS: Final[Mapping[HTTPStatus, str]] = {
    HTTPStatus.BAD_REQUEST: "HTTP境界でリクエストを解釈できない。",
    HTTPStatus.UNAUTHORIZED: "資格情報が無い、または検証できない。",
    HTTPStatus.FORBIDDEN: "主体は判明したが、その操作の権限が無い。",
    HTTPStatus.NOT_FOUND: "対象が存在しない、または他テナントのため隠されている。",
    HTTPStatus.CONFLICT: "一意制約違反や楽観ロック衝突など、既存の状態と衝突する。",
    HTTPStatus.UNPROCESSABLE_CONTENT: "入力値が形式またはドメイン規則を満たさない。",
}

_STATUS_BY_EXCEPTION: Final[Mapping[type[BaseException], HTTPStatus]] = {
    # --- 基底: 個別に載っていないものはここへ落ちる ---
    # 「形式は正しいが業務ルール上そのままでは処理できない」が既定の意味。
    DomainError: HTTPStatus.UNPROCESSABLE_CONTENT,
    ApplicationError: HTTPStatus.UNPROCESSABLE_CONTENT,
    PresentationError: HTTPStatus.BAD_REQUEST,
    # --- 401: 主体がまだ決まっていない ---
    AuthenticationError: HTTPStatus.UNAUTHORIZED,
    # --- 403: 主体は判明したうえでの拒否 ---
    # 別テナントのリソースは TenantBoundaryNotFoundError（404）として隠すので、
    # ここへ来るのは自テナント内の権限不足だけである。
    AuthorizationError: HTTPStatus.FORBIDDEN,
    # --- 404: 未検出とテナント境界 ---
    # コンテキストごとの *NotFoundError は基底がまちまちなので個別に載せる。
    NotFoundError: HTTPStatus.NOT_FOUND,
    CoveragePatientNotFoundError: HTTPStatus.NOT_FOUND,
    PatientCoverageNotFoundError: HTTPStatus.NOT_FOUND,
    DispensingNotFoundError: HTTPStatus.NOT_FOUND,
    DispensingPrescriptionNotFoundError: HTTPStatus.NOT_FOUND,
    DispensingStaffNotFoundError: HTTPStatus.NOT_FOUND,
    DispensingStoreNotFoundError: HTTPStatus.NOT_FOUND,
    MedicationHistoryDispensingNotFoundError: HTTPStatus.NOT_FOUND,
    MedicationHistoryNotFoundError: HTTPStatus.NOT_FOUND,
    MedicationHistoryStaffNotFoundError: HTTPStatus.NOT_FOUND,
    MedicationHistoryStoreNotFoundError: HTTPStatus.NOT_FOUND,
    PatientMedicalProfileNotFoundError: HTTPStatus.NOT_FOUND,
    MedicineNotFoundError: HTTPStatus.NOT_FOUND,
    PatientExternalIdentifierNotFoundError: HTTPStatus.NOT_FOUND,
    PatientNotFoundError: HTTPStatus.NOT_FOUND,
    PrescriptionCoverageSelectionNotFoundError: HTTPStatus.NOT_FOUND,
    PrescriptionNotFoundError: HTTPStatus.NOT_FOUND,
    PrescriptionPatientNotFoundError: HTTPStatus.NOT_FOUND,
    PrescriptionPharmacistNotFoundError: HTTPStatus.NOT_FOUND,
    PrescriptionStoreNotFoundError: HTTPStatus.NOT_FOUND,
    ReceptionPatientNotFoundError: HTTPStatus.NOT_FOUND,
    ReceptionStoreNotFoundError: HTTPStatus.NOT_FOUND,
    StaffApplicationNotFoundError: HTTPStatus.NOT_FOUND,
    StoreNotFoundError: HTTPStatus.NOT_FOUND,
    ConcurrentMedicationNotFoundError: HTTPStatus.NOT_FOUND,
    InquiryNotFoundError: HTTPStatus.NOT_FOUND,
    StaffDomainNotFoundError: HTTPStatus.NOT_FOUND,
    # --- 409: 既存のデータ・状態と衝突する ---
    ConcurrentModificationError: HTTPStatus.CONFLICT,
    CorporateNameAlreadyExistsError: HTTPStatus.CONFLICT,
    CoverageDeactivationAlreadyFixedError: HTTPStatus.CONFLICT,
    CoveragePeriodConflictError: HTTPStatus.CONFLICT,
    DispensingAlreadyExistsError: HTTPStatus.CONFLICT,
    MedicationHistoryAlreadyExistsError: HTTPStatus.CONFLICT,
    MedicationHistoryAlreadyFinalizedError: HTTPStatus.CONFLICT,
    PatientMedicalProfileAlreadyExistsError: HTTPStatus.CONFLICT,
    MedicineEffectivePeriodConflictError: HTTPStatus.CONFLICT,
    PatientExternalIdentifierAlreadyExistsError: HTTPStatus.CONFLICT,
    InquiryAlreadyResolvedError: HTTPStatus.CONFLICT,
    PrescriptionDocumentNumberAlreadyExistsError: HTTPStatus.CONFLICT,
    AffiliationDateConflictError: HTTPStatus.CONFLICT,
    ConcurrentStoreConflictError: HTTPStatus.CONFLICT,
    StaffCodeAlreadyExistsError: HTTPStatus.CONFLICT,
    InsurancePharmacyNumberAlreadyExistsError: HTTPStatus.CONFLICT,
    StoreCodeAlreadyExistsError: HTTPStatus.CONFLICT,
    StoreNameAlreadyExistsError: HTTPStatus.CONFLICT,
}


def status_for_type(error_type: type[TranslatableError]) -> HTTPStatus:
    """例外クラスに対応するHTTPステータスを返す。

    継承の近い順に表を引く。3つの基底が必ず載っているため、翻訳対象の例外で
    あれば必ず解決する。インスタンスではなくクラスを受け取るのは、生成に引数を
    要する例外まで含めて網羅性を検査できるようにするためである。
    """
    for klass in error_type.__mro__:
        status = _STATUS_BY_EXCEPTION.get(klass)
        if status is not None:
            return status
    raise LookupError(f"{error_type.__name__} に対応するHTTPステータスがありません。")


def status_for(error: TranslatableError) -> HTTPStatus:
    """例外に対応するHTTPステータスを返す。"""
    return status_for_type(type(error))


def _json(
    status: HTTPStatus,
    body: ErrorResponse,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=int(status),
        content=body.model_dump(),
        headers=dict(headers) if headers else None,
    )


def to_response(error: TranslatableError) -> JSONResponse:
    """例外を共通の応答本文へ変換する。

    例外の型名やスタックは本文へ載せない。内部構造が漏れるうえ、クライアントが
    実装の詳細に依存し始める。分岐に使えるのは安定した ``code`` だけとする。
    """
    return _json(
        status_for(error),
        ErrorResponse(code=error.code, message=error.message),
    )


async def _translate(request: Request, error: Exception) -> JSONResponse:
    """登録した基底例外を応答へ翻訳する。"""
    del request
    if not isinstance(error, DomainError | ApplicationError | PresentationError):
        raise error  # pragma: no cover - 登録した型以外は届かない
    return to_response(error)


async def _translate_request_validation(
    request: Request, error: Exception
) -> JSONResponse:
    """入力検証の失敗を、他の失敗と同じ形の本文へ翻訳する。

    FastAPI の既定は ``{"detail": [...]}`` で、ドメイン由来の失敗と形が違う。
    同じ422で本文の形が2種類あると、クライアントは422を見ても分岐を書けない。
    項目ごとの内容は ``errors`` に残すが、封筒は他と揃える。
    """
    del request
    if not isinstance(error, RequestValidationError):
        raise error  # pragma: no cover - 登録した型以外は届かない
    return _json(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        ErrorResponse(
            code="REQUEST_VALIDATION_ERROR",
            message="リクエストの内容が正しくありません。",
            # ``loc`` と ``msg`` だけを取り出す。``input`` と ``ctx`` は任意の
            # オブジェクトを含みうるので、そのまま載せるとJSON化で失敗する。
            errors=[
                FieldError(
                    location=".".join(str(part) for part in item["loc"]),
                    message=item["msg"],
                )
                for item in error.errors()
            ],
        ),
    )


async def _translate_http_exception(request: Request, error: Exception) -> JSONResponse:
    """経路解決の失敗（未知のパス・許可されないメソッド）を同じ形へ翻訳する。

    ここを既定のままにすると、存在しないパスだけ ``{"detail": "Not Found"}`` に
    なり、業務の404と形が食い違う。
    """
    del request
    if not isinstance(error, StarletteHTTPException):
        raise error  # pragma: no cover - 登録した型以外は届かない
    status = HTTPStatus(error.status_code)
    return _json(
        status,
        ErrorResponse(
            code=status.name,
            message=_ROUTING_MESSAGES.get(status, str(error.detail)),
        ),
        # 405 の ``Allow`` のように、ステータスと対になるヘッダを落とさない。
        headers=error.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """本文の形を1つに揃えるための翻訳を登録する。

    Domain / Application / Presentation は基底だけを登録する。個別の例外型ごとに
    登録すると、新しい例外を足したときに登録し忘れた分だけが素の500になる。
    """
    for base in (DomainError, ApplicationError, PresentationError):
        app.add_exception_handler(base, _translate)
    app.add_exception_handler(RequestValidationError, _translate_request_validation)
    app.add_exception_handler(StarletteHTTPException, _translate_http_exception)


def error_responses(*statuses: HTTPStatus) -> dict[int | str, dict[str, Any]]:
    """OpenAPI へ載せるエラー応答の定義を作る。

    実際に返すステータスをスキーマへ書かないと、生成クライアントはエラーを型と
    して扱えず、成功応答だけを知ることになる。説明の無いステータスを渡すと
    ``KeyError`` で落ちるので、返しうるステータスと説明の対応は常に揃う。
    """
    return {
        int(status): {
            "model": ErrorResponse,
            "description": _ERROR_DESCRIPTIONS[status],
        }
        for status in statuses
    }


__all__ = [
    "ErrorResponse",
    "FieldError",
    "TranslatableError",
    "error_responses",
    "register_error_handlers",
    "status_for",
    "status_for_type",
    "to_response",
]
