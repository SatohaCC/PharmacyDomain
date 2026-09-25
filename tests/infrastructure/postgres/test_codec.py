"""集約payloadのJSON codecを検査する。"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import pkgutil
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

import pytest

import app.domain
from app.domain.corporate.corporate import Corporate
from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.exceptions import VerificationStatusMismatchError
from app.domain.dispensing.primitives import (
    DispensingCancellationReason,
    DispensingCompletionType,
    DispensingProcessStatus,
    VerificationResult,
    VerificationTimestamp,
)
from app.domain.foundation.exceptions import DomainError
from app.domain.foundation.primitives.base import DomainPrimitive
from app.domain.identity.primitives import AccountPersonId, UserAccountId
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    FinalizationDelayReason,
    FinalizedTimestamp,
    MedicationHistorySourceSystem,
    MedicationHistoryStatus,
)
from app.domain.patient.lifecycle import PatientStatus
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import (
    ExternalPatientId,
    PatientAddress,
    PatientBirthDate,
    PatientGenderCode,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.profile_history import (
    PatientProfileChange,
    PatientProfileChangeSource,
    PatientProfileSnapshot,
)
from app.domain.prescription.exceptions import (
    BlockingInquiryExistsError,
    OpenInquiryExistsError,
)
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import (
    InquiryNumber,
    InquiryResultType,
    PrescriptionStatus,
)
from app.domain.reception.primitives import (
    ReceptionFieldPath,
    ReceptionFingerprint,
    ReceptionId,
)
from app.domain.reception.reception import Reception, ReceptionCorrection
from app.domain.staff.primitives import (
    BaseQualificationProfile,
    DietitianProfile,
    DietitianRegistrationNumber,
    PharmacistLicenseNumber,
    PharmacistProfile,
    RegisteredSellerProfile,
    SellerRegistrationNumber,
    StaffId,
    StaffQualifications,
)
from app.domain.staff.staff import Staff
from app.domain.store.business_hours import (
    BusinessDayException,
    BusinessHours,
    BusinessHourSlot,
    BusinessHoursNote,
    BusinessWeekday,
    StoreOpeningState,
    WeekdayBusinessHours,
)
from app.domain.store.primitives import StoreId
from app.domain.store.store import Store
from app.infrastructure.postgres.codec import (
    QUALIFICATION_PROFILE_TAGS,
    QUALIFICATION_TAG_KEY,
    PersistenceMappingError,
    _primitive_value_type,
    decode_aggregate,
    encode_aggregate,
)
from tests.factories.dispensing_factory import create_dispensing, verify_passed
from tests.factories.medication_history_factory import (
    create_nsips_draft_record,
    create_record,
)
from tests.factories.persistence_factory import create_patient
from tests.factories.prescription_factory import (
    create_prescription,
    create_response,
    start_inquiry,
)
from tests.factories.staff_factory import create_staff
from tests.factories.store_factory import create_store
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


def test_受付の全体指紋と項目指紋が_JSONBを経由して往復できる() -> None:
    """受付訂正履歴の型付き差分情報を保持して復元する。"""
    corporate = create_corporate()
    patient = create_patient(corporate_id=corporate.id)
    store = create_store(corporate_id=corporate.id)
    fingerprint = ReceptionFingerprint("a" * 64)
    field_path = ReceptionFieldPath("prescription.document_number")
    reception = Reception(
        id=ReceptionId.generate(),
        corporate_id=corporate.id,
        store_id=store.id,
        patient_id=patient.id,
        latest_fingerprint=fingerprint,
        field_fingerprints=((field_path, ReceptionFingerprint("b" * 64)),),
        correction_history=(
            ReceptionCorrection(
                fingerprint=fingerprint,
                changed_fields=(field_path,),
                received_at=datetime(2026, 9, 23, tzinfo=UTC),
            ),
        ),
    )

    restored = decode_aggregate(encode_aggregate(reception), Reception)

    assert encode_aggregate(restored) == encode_aggregate(reception)


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


def test_tc43_従来PatientJSONBを新しい任意属性Noneで復元する() -> None:
    """新属性を持たない保存済みPatientを意味変更なしで復元する。"""
    patient = create_patient()
    payload = encode_aggregate(patient)
    for field_name in ("gender", "postal_code", "address", "phone_number"):
        payload.pop(field_name, None)

    restored = decode_aggregate(payload, Patient)

    assert restored.id == patient.id
    assert restored.names == patient.names
    assert restored.birth_date == patient.birth_date
    for field_name in ("gender", "postal_code", "address", "phone_number"):
        assert hasattr(restored, field_name)
        assert getattr(restored, field_name) is None


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


# --------------------------------------------------------------------------
# 資格プロファイルの判別子
# --------------------------------------------------------------------------


def _all_qualification_profiles() -> list[type[BaseQualificationProfile]]:
    """app.domain 配下で定義された資格プロファイルの具象型を集める。"""
    for module in pkgutil.walk_packages(app.domain.__path__, "app.domain."):
        importlib.import_module(module.name)

    found: set[type[BaseQualificationProfile]] = set()

    def walk(cls: type[Any]) -> None:
        for subclass in cls.__subclasses__():
            if not inspect.isabstract(subclass):
                found.add(subclass)
            walk(subclass)

    walk(BaseQualificationProfile)
    return sorted(found, key=lambda cls: cls.__qualname__)


#: 往復検査に使う各資格の代表値。新しい資格クラスを足したらここにも足す。
_PROFILE_SAMPLES: dict[type[BaseQualificationProfile], BaseQualificationProfile] = {
    PharmacistProfile: PharmacistProfile(
        license_number=PharmacistLicenseNumber("123456")
    ),
    # 管理栄養士と登録販売者は必須フィールドが ``registration_number`` だけで
    # 同形になる。同じ値を入れて、判別子なしでは区別できない状況を再現する。
    DietitianProfile: DietitianProfile(
        registration_number=DietitianRegistrationNumber("12345678")
    ),
    RegisteredSellerProfile: RegisteredSellerProfile(
        registration_number=SellerRegistrationNumber("12345678")
    ),
}


def test_全ての資格プロファイルに判別子が登録されている() -> None:
    # 登録を忘れると、保存はできるのに復元だけが失敗する行ができる。
    assert set(_all_qualification_profiles()) == set(
        QUALIFICATION_PROFILE_TAGS.values()
    )


def test_判別子キーは_資格プロファイルのフィールド名と衝突しない() -> None:
    # 衝突すると、判別子を取り除いた残りが本来のフィールドを欠く。
    for profile_type in _all_qualification_profiles():
        names = {field.name for field in dataclasses.fields(profile_type)}
        assert QUALIFICATION_TAG_KEY not in names


def test_全ての資格プロファイルに代表値がある() -> None:
    # 代表値が無い資格は、次の往復検査を素通りしてしまう。
    assert set(_all_qualification_profiles()) == set(_PROFILE_SAMPLES)


@pytest.mark.parametrize("profile_type", list(_PROFILE_SAMPLES))
def test_資格プロファイルは_同じクラスへ復元される(
    profile_type: type[BaseQualificationProfile],
) -> None:
    profile = _PROFILE_SAMPLES[profile_type]
    staff = create_staff(qualifications=StaffQualifications.from_profiles(profile))

    payload = encode_aggregate(staff)
    restored = decode_aggregate(payload, Staff)

    (restored_profile,) = restored.qualifications.profiles
    assert type(restored_profile) is profile_type
    assert restored_profile == profile


def test_判別子のない資格プロファイルは_別の資格として復元しない() -> None:
    # 判別子を書く前に保存された行には、どの資格だったかを決める根拠が無い。
    staff = create_staff(
        qualifications=StaffQualifications.from_profiles(
            _PROFILE_SAMPLES[RegisteredSellerProfile]
        )
    )
    payload = encode_aggregate(staff)
    for item in payload["qualifications"]["_items"]:  # type: ignore[index]
        del item[QUALIFICATION_TAG_KEY]

    with pytest.raises(PersistenceMappingError):
        decode_aggregate(payload, Staff)


def _store_with_hours() -> Store:
    """昼休みと特例日を持つ開局時間を設定した店舗を作る。"""
    weekly = tuple(
        WeekdayBusinessHours(
            weekday=day,
            slots=()
            if day == BusinessWeekday.SUNDAY
            else (
                BusinessHourSlot(opens_at=time(9, 0), closes_at=time(13, 0)),
                BusinessHourSlot(opens_at=time(14, 0), closes_at=time(19, 0)),
            ),
        )
        for day in BusinessWeekday
    )
    hours = BusinessHours(
        weekly=weekly,
        exceptions=(
            BusinessDayException(
                on=date(2026, 12, 31), note=BusinessHoursNote("年末年始")
            ),
        ),
    )
    return create_store().change_business_hours(hours)


def test_開局時間が_JSONBを経由して往復できる() -> None:
    """時刻はJSONに素の型が無いので、文字列との変換を固定する。"""
    # Arrange
    store = _store_with_hours()

    # Act
    restored = decode_aggregate(encode_aggregate(store), Store)

    # Assert
    assert restored.business_hours == store.business_hours
    assert restored.opening_state_at(on=date(2026, 12, 31), at=time(10, 0)) == (
        StoreOpeningState.CLOSED
    )


def test_開局時間の無い古い行も_店舗として復元できる() -> None:
    """既存行のpayloadには開局時間が無い。

    省略できる項目としてdataclassの既定値へ落ちるので、この集約に限っては
    payloadを書き換えるマイグレーションが要らない。その前提をここで固定する。
    """
    # Arrange
    payload = encode_aggregate(create_store())
    del payload["business_hours"]

    # Act
    restored = decode_aggregate(payload, Store)

    # Assert
    assert restored.business_hours is None


def test_TC30_患者集約のcodec往復() -> None:
    """患者集約（ライフサイクル状態・変更履歴を含む）がJSONB往復で完全復元できる。"""
    # Arrange
    patient = create_patient()

    # Act
    encoded = encode_aggregate(patient)
    restored = decode_aggregate(encoded, Patient)

    # Assert
    assert restored.id == patient.id
    assert restored.status == PatientStatus.ACTIVE
    assert restored.merged_into_id is None
    assert restored.status_history == ()


def test_TC31_患者集約_後方互換復元() -> None:
    """statusやmerged_into_idの無い過去のJSONB行も患者として復元できる。"""
    # Arrange: 過去のpayloadをシミュレート
    payload = encode_aggregate(create_patient())
    payload.pop("status", None)
    payload.pop("merged_into_id", None)
    payload.pop("status_history", None)

    # Act
    restored = decode_aggregate(payload, Patient)

    # Assert: dataclassの既定値へ安全にフォールバックすること
    assert restored.status == PatientStatus.ACTIVE
    assert restored.merged_into_id is None
    assert restored.status_history == ()


def test_tc71_患者プロフィール受信履歴のcodec往復と旧payload互換() -> None:
    """受信/手動履歴の前後Snapshotと旧受信payloadを往復する。"""
    patient = create_patient()
    received = PatientProfileSnapshot(
        names=patient.names,
        birth_date=PatientBirthDate(date(1980, 1, 2)),
        gender=PatientGenderCode("1"),
        postal_code=PatientPostalCode("1000001"),
        address=PatientAddress("東京都千代田区新住所"),
        phone_number=PatientPhoneNumber("03-0000-0000"),
    )
    before = PatientProfileSnapshot(
        names=patient.names,
        birth_date=patient.birth_date,
        gender=None,
        postal_code=None,
        address=PatientAddress("東京都千代田区旧住所"),
        phone_number=None,
    )
    change = PatientProfileChange(
        reception_id=ReceptionId.generate(),
        store_id=StoreId.generate(),
        external_patient_id=ExternalPatientId("RECEIPT-42"),
        recorded_at=datetime(2026, 9, 23, 1, 2, 3, tzinfo=UTC),
        changed_fields=("patient.address", "patient.phone_number"),
        source=PatientProfileChangeSource.NSIPS,
        received_profile=received,
        before_profile=before,
        applied_profile=received,
    )
    manual_change = PatientProfileChange(
        source=PatientProfileChangeSource.MANUAL,
        recorded_at=datetime(2026, 9, 24, 1, 2, 3, tzinfo=UTC),
        changed_fields=("patient.address",),
        before_profile=received,
        applied_profile=before,
        person_id=AccountPersonId.generate(),
        account_id=UserAccountId.generate(),
    )
    patient_with_history = dataclasses.replace(
        patient,
        profile_history=(change, manual_change),
    )

    restored = decode_aggregate(encode_aggregate(patient_with_history), Patient)

    assert restored.profile_history == (change, manual_change)
    assert restored.profile_history[0].source == PatientProfileChangeSource.NSIPS
    assert restored.profile_history[0].before_profile == before
    assert restored.profile_history[0].applied_profile == received
    assert restored.profile_history[1].source == PatientProfileChangeSource.MANUAL
    assert restored.profile_history[1].reception_id is None
    assert restored.profile_history[1].store_id is None
    assert restored.profile_history[1].external_patient_id is None
    assert restored.profile_history[1].person_id == manual_change.person_id
    assert restored.profile_history[1].account_id == manual_change.account_id

    old_event_payload = encode_aggregate(patient_with_history)
    serialized_events = old_event_payload["profile_history"]
    assert isinstance(serialized_events, list)
    legacy_serialized_event = serialized_events[0]
    assert isinstance(legacy_serialized_event, dict)
    serialized_events[:] = [legacy_serialized_event]
    for field_name in (
        "source",
        "before_profile",
        "applied_profile",
        "person_id",
        "account_id",
    ):
        legacy_serialized_event.pop(field_name, None)
    restored_legacy_event = decode_aggregate(old_event_payload, Patient)
    assert restored_legacy_event.profile_history[0].source == (
        PatientProfileChangeSource.NSIPS
    )
    assert restored_legacy_event.profile_history[0].received_profile == received
    assert restored_legacy_event.profile_history[0].before_profile is None
    assert restored_legacy_event.profile_history[0].applied_profile is None

    old_payload = encode_aggregate(patient)
    old_payload.pop("profile_history", None)
    restored_old = decode_aggregate(old_payload, Patient)
    assert restored_old.profile_history == ()


def test_TC24_薬歴集約のcodec往復と後方互換復元() -> None:
    """確定メタデータを含む薬歴のJSONB往復と、旧payloadからの後方互換復元ができる。"""
    # Arrange 1: 確定済み薬歴（finalized_at, finalized_by, delay_reason あり）の往復
    record = create_record()
    finalized = record.finalize(
        finalized_at=FinalizedTimestamp(datetime(2026, 8, 25, 10, 0, tzinfo=UTC)),
        finalized_by=StaffId.generate(),
        delay_reason=FinalizationDelayReason("翌日確認のため"),
    )
    encoded = encode_aggregate(finalized)

    # Act 1
    restored = decode_aggregate(encoded, MedicationHistoryRecord)

    # Assert 1
    assert restored.id == finalized.id
    assert restored.status == MedicationHistoryStatus.FINALIZED
    assert restored.finalized_at == finalized.finalized_at
    assert restored.finalized_by == finalized.finalized_by
    assert restored.delay_reason == finalized.delay_reason

    # Arrange 2: 旧形式（確定メタデータフィールドが存在しないpayload）
    legacy_payload = encode_aggregate(create_record())
    legacy_payload.pop("finalized_at", None)
    legacy_payload.pop("finalized_by", None)
    legacy_payload.pop("delay_reason", None)

    # Act 2
    restored_legacy = decode_aggregate(legacy_payload, MedicationHistoryRecord)

    # Assert 2
    assert restored_legacy.status == MedicationHistoryStatus.DRAFT
    assert restored_legacy.finalized_at is None
    assert restored_legacy.finalized_by is None
    assert restored_legacy.delay_reason is None


def test_TC23_薬歴の未記録状態をcodec往復し旧payloadも復元する() -> None:
    """確認済み否定と不明を往復し、旧payloadでは由来を未設定にする。"""
    assessed = create_record(information_sheet_provided=False)
    assessed_round_trip = decode_aggregate(
        encode_aggregate(assessed), MedicationHistoryRecord
    )
    assert assessed_round_trip.information_sheet_provided is False
    assert assessed_round_trip.residual_drug is not None
    assert assessed_round_trip.residual_drug.has_residual_drugs is False

    unassessed = dataclasses.replace(
        create_record(information_sheet_provided=None),
        method=None,
        handbook_status=None,
        residual_drug=None,
        source_system=MedicationHistorySourceSystem("NSIPS"),
    )
    encoded = encode_aggregate(unassessed)
    encoded.pop("source_system")
    legacy = decode_aggregate(encoded, MedicationHistoryRecord)
    assert legacy.source_system is None

    restored = decode_aggregate(encode_aggregate(unassessed), MedicationHistoryRecord)
    assert restored.method is None
    assert restored.handbook_status is None
    assert restored.residual_drug is None
    assert restored.information_sheet_provided is None
    assert restored.source_system is not None
    assert restored.source_system.value == "NSIPS"


def test_tc21_取込下書きをcodec往復し旧payloadも読み込める() -> None:
    imported = create_nsips_draft_record()

    restored = decode_aggregate(encode_aggregate(imported), MedicationHistoryRecord)

    assert restored.counselor_id is None
    assert restored.counseled_at is None
    assert restored.imported_at == imported.imported_at

    legacy_payload = encode_aggregate(create_record())
    legacy_payload.pop("imported_at", None)
    legacy = decode_aggregate(legacy_payload, MedicationHistoryRecord)

    assert legacy.imported_at is None
    assert legacy.counselor_id is not None
    assert legacy.counseled_at is not None
