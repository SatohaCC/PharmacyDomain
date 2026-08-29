"""Prescription集約に関わるドメインサービス。

無状態（Stateless）であり、本物の集約を引数で受け取る。
Repository の ``save()`` 契約と Application の事前チェックの双方から
**同じ実装**を呼ぶことで、規則が2箇所に分かれる事故を防ぐ。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.domain.prescription.exceptions import (
    InquiryPharmacistQualificationError,
    MedicineClassificationMissingError,
    MedicineClassificationUnknownError,
    NarcoticPrescriptionDetailsRequiredError,
    PrescriptionDocumentNumberAlreadyExistsError,
    PublicExpenseBurdenNotCoveredError,
    RefillNotAllowedError,
)
from app.domain.prescription.prescription import Prescription, PrescriptionMedicine
from app.domain.prescription.primitives import PrescriptionSourceType
from app.domain.prescription.value_objects import (
    MedicineClassification,
    MedicineRestrictionFlag,
)
from app.domain.shared.medicine import MedicineIdentifier
from app.domain.shared.public_expense import PublicExpenseBurden
from app.domain.staff.primitives import PharmacistProfile, StaffQualifications


class PrescriptionDocumentNumberUniquenessService:
    """電子処方箋の引換番号が法人内で一意であることを検証する。"""

    def ensure_no_conflict(
        self,
        prescription: Prescription,
        existing_prescriptions: Iterable[Prescription],
    ) -> None:
        """同一法人内で引換番号が重複していないことを検証する。

        **電子処方箋のときだけ**一意性を課す。引換番号は電子処方箋管理サービスが
        発行する一意な番号なので、重複は二重取り込みを意味する。

        紙処方箋の番号は医療機関ごとの採番であり、別の医療機関が同じ番号を
        採番しうる。一意性を課すと正当な処方箋を拒否するため課さない。
        「無効化後に一意キーを再利用できるか」と同じく、**集約ごとではなく
        受領元ごとの業務判断**であり、全称のルールにはしない。

        同じ集約IDの現在行は候補から除外し、自身の状態変更を妨げない。
        """
        if prescription.source_type is not PrescriptionSourceType.ELECTRONIC:
            return
        for existing in existing_prescriptions:
            if existing.id == prescription.id:
                continue
            if existing.source_type is not PrescriptionSourceType.ELECTRONIC:
                continue
            if (
                existing.corporate_id == prescription.corporate_id
                and existing.document_number == prescription.document_number
            ):
                raise PrescriptionDocumentNumberAlreadyExistsError(
                    document_number=prescription.document_number.value
                )


def _resolve_classification(
    medicine: PrescriptionMedicine,
    classifications: Mapping[MedicineIdentifier, MedicineClassification],
) -> MedicineClassification:
    """薬品に対応する分類を取り出す。

    渡されていなければ例外にする。「分類が無いから問題なし」と答えると、
    マスタ未登録の薬品で規制の判定が素通りする。
    """
    classification = classifications.get(medicine.identifier)
    if classification is None:
        raise MedicineClassificationMissingError(medicine_name=medicine.name.value)
    return classification


class NarcoticPrescriptionService:
    """麻薬を含む処方箋に必要な追加情報が揃っているかを検証する。

    「その薬品が麻薬か」は医薬品マスタ側の属性であり、``Prescription`` 集約は
    薬品コードと名称しか持たない。したがって集約の ``validate()`` では判定できず、
    本物の分類を受け取る無状態 Domain Service が担当する。
    """

    def ensure_narcotic_details_present(
        self,
        prescription: Prescription,
        classifications: Mapping[MedicineIdentifier, MedicineClassification],
    ) -> None:
        """麻薬を含むなら麻薬処方箋情報が付いていることを検証する。

        Raises:
            MedicineClassificationMissingError: 処方箋の薬品に対応する分類が
                渡されていない場合。
            MedicineClassificationUnknownError: 麻薬区分が ``UNKNOWN`` の場合。
                判定できないことを失敗として扱う（fail-closed）。
            NarcoticPrescriptionDetailsRequiredError: 麻薬を含むのに
                麻薬処方箋情報が無い場合。
        """
        for medicine in self._all_medicines(prescription):
            classification = _resolve_classification(medicine, classifications)
            if classification.is_narcotic.is_unknown:
                raise MedicineClassificationUnknownError(
                    medicine_name=medicine.name.value
                )
            if classification.is_narcotic is not MedicineRestrictionFlag.YES:
                continue
            if prescription.management_info.narcotic is None:
                raise NarcoticPrescriptionDetailsRequiredError()

    @staticmethod
    def _all_medicines(prescription: Prescription) -> tuple[PrescriptionMedicine, ...]:
        """処方箋に含まれるすべての薬品明細を平坦に返す。"""
        return tuple(medicine for rp in prescription.rps for medicine in rp.medicines)


class RefillEligibilityService:
    """リフィル指示を適用できる処方内容かを検証する。

    判定基準は「投与量に限度が定められている医薬品」および「貼付剤（鎮痛・消炎に
    係る効能効果を有するもので、麻薬・向精神薬であるもの、専ら皮膚疾患に用いる
    ものを除く）」であり、いずれも医薬品マスタ側の属性である。

    **「麻薬・向精神薬・湿布薬」のような例示列挙で実装してはならない。**
    麻薬・向精神薬の貼付剤は「貼付剤」の定義から除外され、別途「投与量に限度が
    定められている医薬品」として扱われるため、例示は必ず基準からずれる。
    """

    def ensure_refill_allowed(
        self,
        prescription: Prescription,
        classifications: Mapping[MedicineIdentifier, MedicineClassification],
    ) -> None:
        """リフィル指示が付いているなら、適用除外の薬品が無いことを検証する。

        リフィル指示が無い処方箋には何も課さない。

        Raises:
            MedicineClassificationMissingError: 分類が渡されていない場合。
            MedicineClassificationUnknownError: 判定に必要な属性が ``UNKNOWN``
                の場合（fail-closed）。
            RefillNotAllowedError: 適用除外の医薬品が含まれている場合。
        """
        if not prescription.management_info.is_refill:
            return
        for rp in prescription.rps:
            for medicine in rp.medicines:
                classification = _resolve_classification(medicine, classifications)
                self._ensure_medicine_allows_refill(medicine, classification)

    @staticmethod
    def _ensure_medicine_allows_refill(
        medicine: PrescriptionMedicine,
        classification: MedicineClassification,
    ) -> None:
        """1薬品がリフィル適用除外に当たらないことを検証する。"""
        if (
            classification.has_dosage_limit.is_unknown
            or classification.is_refill_restricted_patch.is_unknown
        ):
            raise MedicineClassificationUnknownError(medicine_name=medicine.name.value)
        if classification.forbids_refill:
            raise RefillNotAllowedError(medicine_name=medicine.name.value)


class InquiryPharmacistService:
    """疑義照会の実施者が薬剤師資格を持つかを検証する。

    薬剤師かどうかは Staff 集約が持つ事実であり、``Prescription`` 集約は
    ``StaffId`` しか持たない。Staff 集約そのものを Prescription から参照すると
    集約間の直接依存になるため、``StaffQualificationBoundary`` が取り出した
    **本物の ``StaffQualifications``** をこのサービスが受け取る。

    判定をBoundary側へ寄せない。実装ごとに「薬剤師とみなす条件」が分岐する。
    """

    def ensure_pharmacist(self, qualifications: StaffQualifications) -> None:
        """薬剤師資格を保有していることを検証する。

        Raises:
            InquiryPharmacistQualificationError: 薬剤師資格が無い場合。
        """
        if not qualifications.has(PharmacistProfile):
            raise InquiryPharmacistQualificationError()


class PublicExpenseBurdenService:
    """薬品の公費負担区分が患者資格の裏付けを持つかを検証する。

    処方箋は公費の番号を持たず「第一公費が負担する」という枠だけを持つ。
    その枠が実在するかは受付で確定した資格選択にしか無いため、集約単独では
    判定できない。``PublicExpenseAvailabilityBoundary`` が返した枠を受け取る。
    """

    def ensure_burden_is_covered(
        self,
        prescription: Prescription,
        available: PublicExpenseBurden,
    ) -> None:
        """負担ありとした枠がすべて患者資格に存在することを検証する。

        負担区分が付いていない薬品には何も課さない（JAHIS レコードNo.231 は
        処方箋内で全薬品出力または全薬品未出力のいずれかであり、未出力は
        「公費負担なし」を意味する）。

        Raises:
            PublicExpenseBurdenNotCoveredError: 資格に存在しない枠へ負担を
                割り当てている場合。
        """
        for rp in prescription.rps:
            for medicine in rp.medicines:
                burden = medicine.public_expense_burden
                if burden is None:
                    continue
                uncovered = burden.uncovered_slots_against(available)
                if uncovered:
                    raise PublicExpenseBurdenNotCoveredError(
                        medicine_name=medicine.name.value,
                        burden_label="、".join(uncovered),
                    )
