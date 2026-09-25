"""MedicationHistory集約に関わるドメインサービス。

無状態（Stateless）であり、**本物の集約・値オブジェクトを引数で受け取る**。
薬歴単独では判定できない指導者の資格などを検証する。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Final

from app.domain.dispensing.dispensing_process import DispensingProcess
from app.domain.dispensing.primitives import DispensingProcessStatus
from app.domain.medication_history.exceptions import (
    CounselorQualificationError,
    MedicationHistoryAlreadyExistsError,
    PatientMedicalProfileAlreadyExistsError,
    StatutoryRecordSourceMismatchError,
)
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import (
    PatientMedicalProfile,
)
from app.domain.medication_history.primitives import (
    StatutoryDispensingRecordItem,
    StatutoryItemState,
    StatutoryRecordBlocker,
)
from app.domain.medication_history.value_objects import (
    StatutoryItemAssessment,
    StatutoryRecordSource,
    StatutoryRecordSufficiency,
)
from app.domain.staff.primitives import PharmacistProfile, StaffQualifications

#: 記載事項1つの充足状態を判定する関数の形。
StatutoryItemResolver = Callable[
    [MedicationHistoryRecord, DispensingProcess, StatutoryRecordSource],
    StatutoryItemState,
]


class CounselorQualificationService:
    """服薬指導を行った者が薬剤師資格を持つかを検証する。

    薬剤師法第25条の2は情報の提供及び指導の義務を薬剤師に課している。
    薬剤師かどうかは Staff 集約が持つ事実であり、``MedicationHistoryRecord`` は
    ``StaffId`` しか持たないため、Application層の資格 Boundary が取り出した
    **本物の ``StaffQualifications``** をこのサービスが受け取る。
    """

    def ensure_pharmacist(self, qualifications: StaffQualifications) -> None:
        """薬剤師資格を保有していることを検証する。

        Raises:
            CounselorQualificationError: 薬剤師資格が無い場合。
        """
        if not qualifications.has(PharmacistProfile):
            raise CounselorQualificationError()


class MedicationHistoryUniquenessService:
    """同一調剤セッションに確定済の薬歴が2件以上無いことを検証する。"""

    def ensure_no_conflict(
        self,
        record: MedicationHistoryRecord,
        existing_records: Iterable[MedicationHistoryRecord],
    ) -> None:
        """確定済薬歴の重複を検証する。

        **下書きは制限しない。** 書きかけを複数持つのは正当であり、
        制限すると入力途中の記録を作れなくなる。判定対象は確定済どうしだけ。

        同じ集約IDの現在行は候補から除外し、自身の状態変更を妨げない。
        """
        if not record.is_finalized:
            return
        for existing in existing_records:
            if existing.id == record.id or not existing.is_finalized:
                continue
            if (
                existing.corporate_id == record.corporate_id
                and existing.dispensing_id == record.dispensing_id
            ):
                raise MedicationHistoryAlreadyExistsError()


class PatientMedicalProfileUniquenessService:
    """患者ごとに頭書きが1件であることを検証する。"""

    def ensure_no_conflict(
        self,
        profile: PatientMedicalProfile,
        existing_profiles: Iterable[PatientMedicalProfile],
    ) -> None:
        """同一法人・同一患者の頭書きが重複していないことを検証する。

        頭書きが2件あると、どちらが投影結果かが決まらなくなる。
        同じ集約IDの現在行は候補から除外する。
        """
        for existing in existing_profiles:
            if existing.id == profile.id:
                continue
            if (
                existing.corporate_id == profile.corporate_id
                and existing.patient_id == profile.patient_id
            ):
                raise PatientMedicalProfileAlreadyExistsError()


def _recorded_if(condition: bool) -> StatutoryItemState:
    """条件を満たすなら記載済、満たさないなら未記載。

    ``NOT_REQUIRED`` はここから返さない。「該当しない」と言えるのは、事由の
    不発生を源データが積極的に示すときだけで、それは呼び出し側が判断する。
    """
    return StatutoryItemState.RECORDED if condition else StatutoryItemState.MISSING


def _assess_patient_name_and_age(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第一号。氏名は必須項目だが、生年月日は任意なので年齢を書けないことがある。"""
    del record, dispensing
    return _recorded_if(source.patient_birth_date is not None)


def _assess_medicine_name_and_amount(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第二号。調剤した剤と薬品明細の存在は調剤集約の不変条件が保証する。"""
    del record, source
    return _recorded_if(
        bool(dispensing.dispensed_rps)
        and all(rp.medicines for rp in dispensing.dispensed_rps)
    )


def _assess_dispensed_and_counseled_date(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第三号。調剤日と指導日はどちらも必須項目なので、型が存在を保証する。

    それでも表からは外さない。外すと調剤録の記載事項の一覧としての網羅性が
    失われ、将来どちらかが任意になったときに気づけなくなる。
    """
    del source
    return _recorded_if(
        dispensing.dispensed_date is not None and record.counseled_at is not None
    )


def _assess_dispensed_quantity(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第四号。剤ごとの調剤数量は必須項目。"""
    del record, source
    return _recorded_if(
        bool(dispensing.dispensed_rps)
        and all(rp.quantity is not None for rp in dispensing.dispensed_rps)
    )


def _assess_pharmacist_names(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第五号。調剤した薬剤師と指導した薬剤師の**両方**の氏名が要る。

    件数では判定しない。両者が同一人物のこともあり（一人薬剤師体制）、
    無関係なスタッフの氏名がスナップショットに入っていることもある。
    最終鑑査者は第五号の対象ではないので問わない。
    """
    if record.counselor_id is None:
        return StatutoryItemState.MISSING
    return _recorded_if(
        source.find_pharmacist(dispensing.dispenser_id) is not None
        and source.find_pharmacist(record.counselor_id) is not None
    )


def _assess_counseling_summary(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第六号。読まれるのは追記後の実効SOAPなので、そちらで判定する。"""
    del dispensing, source
    return _recorded_if(record.effective_soap.empty_section_label is None)


def _assess_prescription_issued_date(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第七号。処方箋の交付日は必須項目。"""
    del record, dispensing
    return _recorded_if(source.prescription_issued_date is not None)


def _assess_prescriber_name(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第八号。処方医の漢字氏名は必須項目。"""
    del record, dispensing
    return _recorded_if(source.prescriber_names is not None)


def _assess_medical_institution_location(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第九号。名称は必須だが**所在地は任意項目**なので、実際に欠けうる。"""
    del record, dispensing
    return _recorded_if(
        source.medical_institution_name is not None
        and source.medical_institution_address is not None
    )


def _assess_change_and_inquiry_detail(
    record: MedicationHistoryRecord,
    dispensing: DispensingProcess,
    source: StatutoryRecordSource,
) -> StatutoryItemState:
    """第十号（第15条第一号・第二号）。3値すべてが起きる唯一の記載事項。

    変更調剤も疑義照会も起きていなければ該当なし。起きていれば、その内容が
    再現できるかを見る。代替調剤の理由は任意項目なので欠けうるが、減数調剤の
    理由は型が必須にしているのでつねに残る。疑義照会は1件でも未回答なら、
    回答内容を記載できない。
    """
    del record
    substituted = dispensing.substituted_medicines
    adjusted = tuple(rp for rp in dispensing.dispensed_rps if rp.is_quantity_adjusted)
    if not substituted and not adjusted and not source.inquiries:
        return StatutoryItemState.NOT_REQUIRED
    return _recorded_if(
        all(
            medicine.substitution is not None
            and medicine.substitution.reason is not None
            for medicine in substituted
        )
        and all(inquiry.has_response for inquiry in source.inquiries)
    )


#: 記載事項ごとの判定。列挙との一致はモジュール読み込み時に検査する。
STATUTORY_ITEM_RESOLVERS: Final[
    Mapping[StatutoryDispensingRecordItem, StatutoryItemResolver]
] = {
    StatutoryDispensingRecordItem.PATIENT_NAME_AND_AGE: _assess_patient_name_and_age,
    StatutoryDispensingRecordItem.MEDICINE_NAME_AND_AMOUNT: (
        _assess_medicine_name_and_amount
    ),
    StatutoryDispensingRecordItem.DISPENSED_AND_COUNSELED_DATE: (
        _assess_dispensed_and_counseled_date
    ),
    StatutoryDispensingRecordItem.DISPENSED_QUANTITY: _assess_dispensed_quantity,
    StatutoryDispensingRecordItem.PHARMACIST_NAMES: _assess_pharmacist_names,
    StatutoryDispensingRecordItem.COUNSELING_SUMMARY: _assess_counseling_summary,
    StatutoryDispensingRecordItem.PRESCRIPTION_ISSUED_DATE: (
        _assess_prescription_issued_date
    ),
    StatutoryDispensingRecordItem.PRESCRIBER_NAME: _assess_prescriber_name,
    StatutoryDispensingRecordItem.MEDICAL_INSTITUTION_LOCATION: (
        _assess_medical_institution_location
    ),
    StatutoryDispensingRecordItem.CHANGE_AND_INQUIRY_DETAIL: (
        _assess_change_and_inquiry_detail
    ),
}

if set(STATUTORY_ITEM_RESOLVERS) != set(StatutoryDispensingRecordItem):
    raise RuntimeError("調剤録の記載事項の判定表に定義漏れがあります。")


class StatutoryDispensingRecordService:
    """薬歴が調剤録の記載事項を満たすかを判定する。

    薬剤師法第28条の調剤録の記載事項（施行規則第16条第1項）は、薬歴・調剤・
    処方箋・患者に分かれて存在する。処方箋集約と患者集約は本コンテキストから
    参照できないため、それらの事実は不変スナップショットで受け取る。

    **報告であって強制ではない。** 記載が足りない薬歴の確定を止めはしない。
    """

    def verify(
        self,
        record: MedicationHistoryRecord,
        dispensing: DispensingProcess,
        source: StatutoryRecordSource,
    ) -> StatutoryRecordSufficiency:
        """記載事項ごとの充足状態と、代替を妨げる要因を判定する。

        妨げる要因があっても記載事項の判定は打ち切らない。打ち切ると、直すべき点が
        一度に1つしか見えない。

        Raises:
            StatutoryRecordSourceMismatchError: 3者が同じ1件を指していない場合。
        """
        self._ensure_same_subject(record, dispensing, source)
        return StatutoryRecordSufficiency(
            assessments=tuple(
                StatutoryItemAssessment(
                    item=item, state=resolve(record, dispensing, source)
                )
                for item, resolve in STATUTORY_ITEM_RESOLVERS.items()
            ),
            blockers=self._blockers(record, dispensing),
        )

    def _ensure_same_subject(
        self,
        record: MedicationHistoryRecord,
        dispensing: DispensingProcess,
        source: StatutoryRecordSource,
    ) -> None:
        """3者が同じ1件の調剤を指していることを保証する。

        集約IDの一致だけでは足りない。法人・患者・処方箋のどれかが食い違えば、
        別の調剤の記載事項を継ぎ接ぎした「充足」になる。

        スナップショットは処方箋だけでなく**患者も照合する**。患者の氏名と年齢
        （第一号）はスナップショットだけから判定されるので、照合を落とすと別人の
        氏名を根拠に充足したと報告できてしまう。
        """
        if (
            record.dispensing_id != dispensing.id
            or record.corporate_id != dispensing.corporate_id
            or record.patient_id != dispensing.patient_id
            or record.prescription_id != dispensing.prescription_id
            or record.patient_id != source.patient_id
            or record.prescription_id != source.prescription_id
        ):
            raise StatutoryRecordSourceMismatchError()

    def _blockers(
        self,
        record: MedicationHistoryRecord,
        dispensing: DispensingProcess,
    ) -> tuple[StatutoryRecordBlocker, ...]:
        """記載事項とは別軸で、調剤録の代替を妨げる要因を並べる。

        確定していない薬歴はいつでも書き換えられるので、記載がそろっていても
        調剤録にならない。交付前・中止の調剤も同じく、調剤の事実が確定していない。
        """
        blockers: list[StatutoryRecordBlocker] = []
        if not record.is_finalized:
            blockers.append(StatutoryRecordBlocker.MEDICATION_HISTORY_NOT_FINALIZED)
        if dispensing.status is not DispensingProcessStatus.COMPLETED:
            blockers.append(StatutoryRecordBlocker.DISPENSING_NOT_COMPLETED)
        return tuple(blockers)
