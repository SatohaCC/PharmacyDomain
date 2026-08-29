"""用法（服用・使用の指示）の共有語彙（Shared Kernel）。

処方箋・調剤・薬歴のいずれもが用法を持つ。用法は**どの集約の同一性でもない**
所有者のいない語彙なので、所有コンテキストから import させると依存の向きが
語彙の実態と食い違う（``PatientId`` のような集約の同一性とは扱いを変える）。
``medicine.py`` の薬品語彙と同じ判断基準による。

出典は2系統あるため、番号だけでなく規格名と版を併記する。

- JAHIS 院外処方箋２次元シンボル記録条件規約 Ver.1.11 レコードNo.111（用法レコード）
- 厚労省 電子処方箋管理サービス 記録条件仕様（処方編）Ver.2.4 用法レコード

用法**補足**（別表14）は処方箋固有の概念なので、ここではなく
``app/domain/prescription/`` に置く。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from app.base.domain.exceptions import DomainValidationError
from app.base.domain.primitives.primitives import (
    BaseNormalizedString,
    BasePositiveInt,
)
from app.base.domain.value_object import ValueObject


class DosageCodeType(StrEnum):
    """用法コード種別。

    JAHIS レコードNo.111 は「1:コードなし, 2:JAMI用法コード, 3〜8:将来統一
    コードを想定」。処方編の用法レコードは「``3``（電子処方箋用法マスタ）固定」。
    **紙と電子で使える値が異なる。**
    """

    NONE = "none"
    JAMI = "jami"
    EP_MASTER = "ep_master"

    @property
    def record_code(self) -> str:
        """規格のレコードへ記録する数字コード。"""
        return {self.NONE: "1", self.JAMI: "2", self.EP_MASTER: "3"}[self]

    @property
    def label(self) -> str:
        """画面表示・帳票出力用の日本語名称。"""
        labels = {
            self.NONE: "コードなし",
            self.JAMI: "JAMI用法コード",
            self.EP_MASTER: "電子処方箋用法マスタ",
        }
        return labels[self]


class DosageCode(BaseNormalizedString):
    """用法コード。JAHIS・処方編とも ``X16``（16桁）。

    JAMI（日本医療情報学会）の処方・注射オーダ標準用法規格、または
    電子処方箋用法マスタのコード。例: ``1013044400000000``。
    """

    def validate(self) -> None:
        super().validate()
        if len(self.value) != 16:
            raise DomainValidationError("用法コードは16桁で指定してください。")


class DosageName(BaseNormalizedString):
    """用法名称。JAHIS は ``N50``、処方編は ``N150``。広い方に合わせる。"""

    def validate(self) -> None:
        super().validate()
        if len(self.value) > 150:
            raise DomainValidationError("用法名称は150文字以内で指定してください。")


class DailyFrequency(BasePositiveInt):
    """1日回数。JAHIS レコードNo.111 のフィールドは ``92 2`` なので 1〜99。"""

    def validate(self) -> None:
        super().validate()
        if self.value > 99:
            raise DomainValidationError("1日回数は99以内で指定してください。")


@dataclass(frozen=True, kw_only=True)
class DosageInstruction(ValueObject):
    """用法（JAHIS レコードNo.111 / 処方編 用法レコード）。

    調剤側でも同じ値を持つ。減数調剤は「用法及び用量の変更は行わずに投与日数等を
    減らす調剤」なので、調剤結果の用法は処方箋の用法と一致する。
    """

    code_type: DosageCodeType
    name: DosageName
    code: DosageCode | None = None
    daily_frequency: DailyFrequency | None = None

    _FIELD_LABELS: ClassVar[Mapping[str, str]] = {
        "code_type": "用法コード種別",
        "name": "用法名称",
        "code": "用法コード",
        "daily_frequency": "1日回数",
    }

    def validate(self) -> None:
        """コード種別とコードの有無の整合性を検証する。

        ``MedicineIdentifier`` と同じ形の検証であり、コンテキスト固有の業務例外
        ではなく ``DomainValidationError`` を送出する（Shared Kernel は各
        コンテキストの例外型を知らない）。
        """
        if self.code_type is DosageCodeType.NONE:
            if self.code is not None:
                raise DomainValidationError(
                    "用法コード種別が「コードなし」のときは用法コードを指定できません。"
                )
            return
        if self.code is None:
            raise DomainValidationError(
                f"用法コード種別が「{self.code_type.label}」のときは"
                "用法コードが必要です。"
            )
