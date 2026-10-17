"""利用側が所有する不変の参照情報。元コンテキストの実装型は保持しない。"""

from __future__ import annotations

from enum import StrEnum

from app.domain.foundation.exceptions import DomainValidationError
from app.domain.foundation.primitives.primitives import (
    BaseAddress,
    BaseDate,
    BaseNormalizedString,
    BasePositiveInt,
)


class MedicineName(BaseNormalizedString):
    """薬品名称。

    医薬品マスタの表示名だけでなく、未収載薬・OTC・健康食品の名称も表す。
    この値を持つことは医薬品マスタ行の存在を意味しない。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 180:
            raise DomainValidationError("薬品名称は180文字以内で指定してください。")


class PatientBirthDate(BaseDate):
    """患者の生年月日。"""


class MedicalInstitutionName(BaseNormalizedString):
    """医療機関名称。JAHIS レコードNo.1 で ``N60``（漢字半角混在可）。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 60:
            raise DomainValidationError("医療機関名称は60文字以内で指定してください。")


class MedicalInstitutionAddressLine(BaseAddress):
    """医療機関の所在地。"""


class PrescriptionIssuedDate(BaseDate):
    """処方箋交付年月日。"""


class InquiryNumber(BasePositiveInt):
    """疑義照会の連番。

    規格（調剤編 511）は「複数記録可（最大999）」なので上限を999に揃える。
    99に絞る業務上の根拠がない。
    """

    def validate(self) -> None:
        super().validate()
        if self.value > 999:
            raise DomainValidationError("照会連番は999以内で指定してください。")


class DispensingProcessStatus(StrEnum):
    """調剤セッションの状態。"""

    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.IN_PROGRESS: "調剤調製中",
            self.VERIFIED: "最終鑑査済（交付待ち）",
            self.COMPLETED: "交付済",
            self.CANCELLED: "調剤中止",
        }
        return labels[self]

    @property
    def is_terminal(self) -> bool:
        """これ以上状態が動かない終端か。"""
        return self in {
            DispensingProcessStatus.COMPLETED,
            DispensingProcessStatus.CANCELLED,
        }
