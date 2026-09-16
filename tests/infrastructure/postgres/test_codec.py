"""集約payloadのJSON codecを検査する。"""

from __future__ import annotations

import importlib
import pkgutil
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

import app.domain
from app.domain.corporate.corporate import Corporate
from app.domain.dispensing import (
    DispensingCancellationReason,
    DispensingCompletionType,
    DispensingProcess,
    DispensingProcessStatus,
    VerificationResult,
    VerificationStatusMismatchError,
    VerificationTimestamp,
)
from app.domain.foundation.exceptions import DomainError
from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.prescription import (
    BlockingInquiryExistsError,
    InquiryNumber,
    InquiryResultType,
    OpenInquiryExistsError,
    PrescriptionStatus,
)
from app.domain.prescription.prescription import Prescription
from app.domain.staff.primitives import StaffId
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    _primitive_value_type,
    decode_aggregate,
    encode_aggregate,
)
from tests.factories.dispensing_factory import create_dispensing, verify_passed
from tests.factories.prescription_factory import (
    create_prescription,
    create_response,
    start_inquiry,
)
from tests.infrastructure.postgres.helpers import create_corporate

# codec が復元できる Primitive の値型。ここに無い型の Primitive を足すと
# test_全てのドメインプリミティブが_復元できる値型を持つ が落ちる。
_DECODABLE_VALUE_TYPES = frozenset({uuid.UUID, datetime, date, Decimal, int, str, bool})


def _all_domain_primitives() -> list[type[Any]]:
    """app.domain 配下で定義された DomainPrimitive の派生型をすべて集める。"""
    for module in pkgutil.walk_packages(app.domain.__path__, "app.domain."):
        importlib.import_module(module.name)

    found: set[type[Any]] = set()

    def walk(cls: type[Any]) -> None:
        for subclass in cls.__subclasses__():
            found.add(subclass)
            walk(subclass)

    walk(DomainPrimitive)
    return sorted(found, key=lambda cls: f"{cls.__module__}.{cls.__qualname__}")


def test_法人が_JSONBを経由して往復できる() -> None:
    """検索列は複製にすぎず、集約の正はpayloadである。"""
    # Arrange
    corporate = create_corporate()

    # Act
    restored = decode_aggregate(encode_aggregate(corporate), Corporate)

    # Assert
    assert encode_aggregate(restored) == encode_aggregate(corporate)


def test_処方箋が_JSONBを経由して往復できる() -> None:
    """入れ子のRp・用量・日付まで含めて元の値へ戻る。"""
    # Arrange
    prescription = create_prescription()

    # Act
    restored = decode_aggregate(encode_aggregate(prescription), Prescription)

    # Assert
    assert encode_aggregate(restored) == encode_aggregate(prescription)


def test_調剤セッションが_JSONBを経由して往復できる() -> None:
    """調剤内容と監査記録を保ったまま復元できる。"""
    # Arrange
    process = create_dispensing()

    # Act
    restored = decode_aggregate(encode_aggregate(process), DispensingProcess)

    # Assert
    assert encode_aggregate(restored) == encode_aggregate(process)


@pytest.mark.parametrize(
    "primitive", _all_domain_primitives(), ids=lambda c: c.__name__
)
def test_全てのドメインプリミティブが_復元できる値型を持つ(
    primitive: type[Any],
) -> None:
    """基底クラスの並びではなく型引数で判定するので、新しい型も取りこぼさない。"""
    # Arrange & Act
    value_type = _primitive_value_type(primitive)

    # Assert
    assert value_type in _DECODABLE_VALUE_TYPES, (
        f"{primitive.__qualname__} の値型 {value_type} は codec が復元できません。"
    )


def test_未知のフィールドを含むpayloadは_復元を拒否する() -> None:
    """列を消したのにpayloadが残っている、という食い違いを黙って通さない。"""
    # Arrange
    payload = encode_aggregate(create_corporate())
    payload["未知の項目"] = "値"

    # Act & Assert
    with pytest.raises(PersistenceMappingError):
        decode_aggregate(payload, Corporate)


def test_必須フィールドが欠けたpayloadは_復元を拒否する() -> None:
    """欠損を既定値で埋めると、保存されていない事実を作ってしまう。"""
    # Arrange
    payload = encode_aggregate(create_corporate())
    del payload["name"]

    # Act & Assert
    with pytest.raises(PersistenceMappingError):
        decode_aggregate(payload, Corporate)


def test_型の合わないpayloadは_復元を拒否する() -> None:
    """UUID列に数値が入っていたら、集約を作る前に落とす。"""
    # Arrange
    payload = encode_aggregate(create_corporate())
    payload["id"] = 12345

    # Act & Assert
    with pytest.raises(PersistenceMappingError):
        decode_aggregate(payload, Corporate)


def test_JSONBへ変換できない値は_保存を拒否する() -> None:
    """暗黙にstrへ落とすと、復元時に別の値になる。"""

    # Arrange
    class NotEncodable:
        pass

    # Act & Assert
    with pytest.raises(PersistenceMappingError):
        encode_aggregate(NotEncodable())


def test_区分値が不正なpayloadは_復元を拒否する() -> None:
    """列挙にない状態を復元すると、その後の遷移判定がすべて狂う。"""
    # Arrange
    payload = encode_aggregate(create_corporate())
    payload["status"] = "存在しない状態"

    # Act & Assert
    with pytest.raises(PersistenceMappingError):
        decode_aggregate(payload, Corporate)


def test_日時は_タイムゾーン付きのまま往復する() -> None:
    """UTCの情報が落ちると、監査記録の時刻がずれる。"""
    # Arrange
    process = create_dispensing()
    payload = encode_aggregate(process)

    # Act
    restored = decode_aggregate(payload, DispensingProcess)

    # Assert
    encoded = encode_aggregate(restored)
    assert encoded == payload
    assert datetime.now(UTC).tzinfo is not None


@pytest.mark.parametrize("blocking", [False, True], ids=["未回答", "削除回答"])
def test_照会と状態が矛盾する処方payloadは_復元できない(blocking: bool) -> None:
    original = start_inquiry(create_prescription())
    expected: type[DomainError] = OpenInquiryExistsError
    if blocking:
        original = original.resolve_inquiry(
            inquiry_number=InquiryNumber(1),
            response=create_response(result_type=InquiryResultType.DELETED),
        )
        expected = BlockingInquiryExistsError
    payload = encode_aggregate(original)
    payload["status"] = PrescriptionStatus.READY_FOR_DISPENSING.value
    with pytest.raises(expected):
        decode_aggregate(payload, Prescription)


@pytest.mark.parametrize(
    ("status", "result"),
    [
        (DispensingProcessStatus.VERIFIED, None),
        (DispensingProcessStatus.VERIFIED, VerificationResult.FAILED),
        (DispensingProcessStatus.COMPLETED, None),
        (DispensingProcessStatus.COMPLETED, VerificationResult.FAILED),
        (DispensingProcessStatus.IN_PROGRESS, VerificationResult.PASSED),
    ],
)
def test_鑑査と状態が矛盾する調剤payloadは_復元できない(
    status: DispensingProcessStatus, result: VerificationResult | None
) -> None:
    original = create_dispensing()
    if result is not None:
        original = original.verify(
            verifier_id=StaffId.generate(),
            verified_at=VerificationTimestamp(datetime(2026, 8, 24, 2, 0, tzinfo=UTC)),
            result=result,
        )
    payload = encode_aggregate(original)
    payload["status"] = status.value
    with pytest.raises(VerificationStatusMismatchError):
        decode_aggregate(payload, DispensingProcess)


@pytest.mark.parametrize("history", ["調剤完了", "調剤取消", "処方取消"])
def test_完了と取消の履歴は_JSONで保持される(history: str) -> None:
    if history == "処方取消":
        prescription = start_inquiry(create_prescription()).cancel()
        payload = encode_aggregate(prescription)
        assert encode_aggregate(decode_aggregate(payload, Prescription)) == payload
        return
    process = verify_passed(create_dispensing())
    if history == "調剤完了":
        process = process.complete(completion_type=DispensingCompletionType.COMPLETED)
    else:
        process = process.cancel(DispensingCancellationReason("患者都合で中止した。"))
    payload = encode_aggregate(process)
    assert encode_aggregate(decode_aggregate(payload, DispensingProcess)) == payload
