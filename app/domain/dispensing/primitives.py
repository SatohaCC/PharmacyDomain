"""Dispensingコンテキストの識別子・調剤情報プリミティブ。

規格の出典は2系統ある（``okf/rules.md`` §4.5 のとおり規格名まで書く）。

- 厚労省 電子処方箋管理サービス 記録条件仕様（調剤編）Ver.2.2 … レコード番号と別表1〜7
- 厚労省 保険調剤の理解のために（令和8年度）… リフィル・分割調剤・減数調剤の要件

**変更調剤に対応する規格上のコード体系は存在しない。** 調剤編の別表は
1:性別 / 2:患者特記種別 / 3:都道府県 / 4:点数表 / 5:剤形コード / 6:伝達事項種別 /
7:疑義照会種別 の7つだけで、「後発品へ変更した」ことを表すコードは無い。
:class:`SubstitutionCategory` などは調剤録・レセプト・薬歴が必要とする
**ドメイン固有の概念**であり、規格の写像ではない。

薬品そのものの語彙（``MedicineName`` / ``DosageAmount`` 等）は所有者がいないため
Shared Kernel の ``app/base/domain/medicine.py`` にある。
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from app.base.domain.primitives.primitives import (
    BaseAwareTimestamp,
    BaseDate,
    BaseFreeText,
    BasePositiveInt,
    EntityUUID,
)

# --------------------------------------------------------------------------
# 識別子
# --------------------------------------------------------------------------


class DispensingId(EntityUUID):
    """調剤セッション集約の一意識別子（UUIDv7）。"""

    identifier_name = "調剤セッションID"


# --------------------------------------------------------------------------
# 調剤回数と分割理由
# --------------------------------------------------------------------------


class DispensingIteration(BasePositiveInt):
    """1枚の処方箋に対する何回目の調剤かを表す回数。

    **上限はこの型では課さない。** 上限は分割理由ごとに異なり
    （注10は2回・注11は3回・注9は定めなし）、リフィルでは処方箋側の
    総使用回数に従う。型の不変条件にすると、上限の無い注9を表現できない。
    範囲の判定は :class:`DispensingSplitReason` と Domain Service が担う。
    """

    quantity_name: ClassVar[str] = "調剤回数"


class DispensingSplitReason(StrEnum):
    """分割調剤の理由（調剤基本料の注9・注10・注11）。

    出典: 保険調剤の理解のために（令和8年度）。

    **リフィル処方箋はここに含めない。** リフィルは処方箋側の指示
    （``Prescription.management_info.refill``）であり、分割調剤とは回数の
    根拠も算定方法も異なる。同じ列挙に混ぜると、どちらの上限を適用するかが
    呼び出し側の判断になる。
    """

    LONG_TERM_STORAGE = "long_term_storage"
    GENERIC_TRIAL = "generic_trial"
    PRESCRIBER_INSTRUCTED = "prescriber_instructed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.LONG_TERM_STORAGE: "長期保存の困難性等による分割調剤",
            self.GENERIC_TRIAL: "後発医薬品の試用のための分割調剤",
            self.PRESCRIBER_INSTRUCTED: "医師の分割指示による分割調剤",
        }
        return labels[self]

    @property
    def note_number(self) -> str:
        """調剤基本料における注番号。"""
        numbers = {
            self.LONG_TERM_STORAGE: "9",
            self.GENERIC_TRIAL: "10",
            self.PRESCRIBER_INSTRUCTED: "11",
        }
        return numbers[self]

    @property
    def iteration_range(self) -> tuple[int, int | None]:
        """許容される調剤回数の範囲 ``(下限, 上限)``。上限なしは ``None``。"""
        return _SPLIT_ITERATION_RANGES[self]

    def allows_iteration(self, iteration: int) -> bool:
        """指定の調剤回数がこの分割理由で成立するかを返す。"""
        minimum, maximum = self.iteration_range
        if iteration < minimum:
            return False
        return maximum is None or iteration <= maximum

    @property
    def allowed_range_label(self) -> str:
        """許容範囲の表示用文字列。"""
        minimum, maximum = self.iteration_range
        if maximum is None:
            return f"{minimum}回目以降"
        if minimum == maximum:
            return f"{minimum}回目のみ"
        return f"{minimum}〜{maximum}回目"


#: 分割理由ごとの調剤回数の範囲。判定を分割理由ごとの ``if`` で書くと、
#: 理由が増えたときに必ず書き漏れる。
_SPLIT_ITERATION_RANGES: dict[DispensingSplitReason, tuple[int, int | None]] = {
    # 注9: 14日分を超える投薬で2回目以降に成立する。回数上限の定めなし。
    DispensingSplitReason.LONG_TERM_STORAGE: (2, None),
    # 注10: 「2回目の調剤を行った場合に限り」＝実質2分割。
    DispensingSplitReason.GENERIC_TRIAL: (1, 2),
    # 注11: 3分割まで。
    DispensingSplitReason.PRESCRIBER_INSTRUCTED: (1, 3),
}

if set(_SPLIT_ITERATION_RANGES) != set(DispensingSplitReason):
    raise RuntimeError("DispensingSplitReason の回数範囲表に定義漏れがあります。")


class DispensedDate(BaseDate):
    """調剤を行った年月日（業務日）。"""


class NextDispensingDate(BaseDate):
    """次回調剤予定日。

    出典: 調剤編 ``リフィル処方箋情報レコード(521)``。調剤終了区分に ``2``
    （継続）を記録した場合に記録する。**薬局が記録する値であり、投薬期間から
    計算した値ではない。** リフィル2回目以降の前後7日判定はこの値を基準にする。
    """


# --------------------------------------------------------------------------
# 監査時刻
# --------------------------------------------------------------------------


class DispensingTimestamp(BaseAwareTimestamp):
    """調剤セッションを開始したUTC時刻。"""

    timestamp_name: ClassVar[str] = "調剤開始日時"


class AuditTimestamp(BaseAwareTimestamp):
    """処方鑑査を行ったUTC時刻。"""

    timestamp_name: ClassVar[str] = "処方鑑査日時"


class VerificationTimestamp(BaseAwareTimestamp):
    """最終鑑査（調剤鑑査）を行ったUTC時刻。"""

    timestamp_name: ClassVar[str] = "最終鑑査日時"


# --------------------------------------------------------------------------
# 変更調剤の3軸
# --------------------------------------------------------------------------


class SubstitutionCategory(StrEnum):
    """軸1: 代替調剤の種別。処方薬品**そのものを置き換えた**場合だけ記録する。

    **「処方どおり」を表す値は持たない。** 処方どおりなら
    ``DispensedMedicine.substitution is None`` である。両方あると同じ事実に
    2通りの表現ができ、集計時にどちらを数えるかが規約になる。
    """

    GENERIC_SUBSTITUTION = "generic_substitution"
    STRENGTH_CHANGE = "strength_change"
    DOSAGE_FORM_CHANGE = "dosage_form_change"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.GENERIC_SUBSTITUTION: "後発医薬品への変更調剤",
            self.STRENGTH_CHANGE: "規格変更調剤",
            self.DOSAGE_FORM_CHANGE: "剤形変更調剤",
        }
        return labels[self]


class QuantityAdjustmentReason(StrEnum):
    """軸2: 数量調整の理由。

    保険調剤の理解のために（令和8年度）の定義: 「処方箋に記載された医薬品に
    ついて、用法及び用量の変更は行わずに投与日数等を減らす調剤（減数調剤）」。
    """

    RESIDUAL_DRUG = "residual_drug"
    INQUIRY_AGREED = "inquiry_agreed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.RESIDUAL_DRUG: "残薬確認に基づく減数調剤",
            self.INQUIRY_AGREED: "疑義照会の合意による数量変更",
        }
        return labels[self]


class PreparationMethod(StrEnum):
    """軸3: 調製方法。薬品自体は処方どおりで、調製の仕方が加わるもの。

    複数同時に成立する（一包化しつつ粉砕する等）。**加算の排他ルールは
    ここに持たない。** 算定可否は Claim コンテキストの責務であり、ここで
    排他にすると実施した事実を記録できなくなる。
    """

    UNIT_DOSE_PACKAGED = "unit_dose_packaged"
    COMPOUNDED = "compounded"
    MEASURED_MIXING = "measured_mixing"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.UNIT_DOSE_PACKAGED: "一包化",
            self.COMPOUNDED: "自家製剤",
            self.MEASURED_MIXING: "計量混合",
        }
        return labels[self]


class SubstitutionReason(BaseFreeText):
    """代替調剤を行った理由の自由記述。"""


# --------------------------------------------------------------------------
# 鑑査
# --------------------------------------------------------------------------


class VerificationResult(StrEnum):
    """最終鑑査（調剤鑑査）の結果。"""

    PASSED = "passed"
    FAILED = "failed"

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.PASSED: "合格", self.FAILED: "不合格"}
        return labels[self]

    @property
    def is_passed(self) -> bool:
        """合格か。"""
        return self is VerificationResult.PASSED


class AuditNotes(BaseFreeText):
    """処方鑑査の所見。"""


class VerificationNotes(BaseFreeText):
    """最終鑑査の所見。"""


class DispensingCancellationReason(BaseFreeText):
    """調剤中止の理由。"""


# --------------------------------------------------------------------------
# 状態
# --------------------------------------------------------------------------


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


class DispensingCompletionType(StrEnum):
    """調剤終了区分。

    出典: 調剤編 ``リフィル処方箋情報レコード(521)``。

    ``COMPLETED`` は「調剤回数が総使用回数に達した場合**または達していないが
    次回以降の調剤が不要となった場合**」であり、回数だけでは決まらない。
    ``Prescription`` を調剤済へ遷移させる契機はこの区分であって、
    ``iteration == total_refill_count`` ではない。
    """

    COMPLETED = "completed"
    CONTINUES = "continues"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        codes = {self.COMPLETED: "1", self.CONTINUES: "2"}
        return codes[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {self.COMPLETED: "調剤終了", self.CONTINUES: "調剤継続"}
        return labels[self]

    @property
    def requires_next_date(self) -> bool:
        """次回調剤予定日の記録が必要か。"""
        return self is DispensingCompletionType.CONTINUES
