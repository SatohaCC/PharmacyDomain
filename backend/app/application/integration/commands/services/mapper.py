"""Applicationのmapperを定義する。"""

from __future__ import annotations

from app.application.integration.boundary_models import NsipsBundle
from app.application.patient.commands.models import RegisterPatientCommand


class NsipsDataMapper:
    """NsipsBundle からドメイン層の Command を生成する。"""

    @staticmethod
    def to_patient_command(
        bundle: NsipsBundle, corporate_id: str
    ) -> RegisterPatientCommand:
        """患者登録コマンドへ変換する。"""
        kanji = bundle.patient.kanji_name.strip()
        kana = bundle.patient.kana_name.strip()
        last_name, first_name = NsipsDataMapper._split_name(kanji)
        last_kana, first_kana = NsipsDataMapper._split_name(kana)
        return RegisterPatientCommand(
            corporate_id=corporate_id,
            last_name=last_name,
            first_name=first_name,
            last_name_kana=last_kana,
            first_name_kana=first_kana,
            birth_date=bundle.patient.birth_date,
            gender=bundle.patient.gender,
            postal_code=bundle.patient.postal_code,
            address=bundle.patient.address,
            phone_number=bundle.patient.phone_number,
        )

    @staticmethod
    def _split_name(full_name: str) -> tuple[str, str]:
        if " " in full_name:
            parts = full_name.split(" ", 1)
            return (parts[0], parts[1])
        if "\u3000" in full_name:
            parts = full_name.split("\u3000", 1)
            return (parts[0], parts[1])
        if len(full_name) >= 4:
            return (full_name[:2], full_name[2:])
        if len(full_name) >= 2:
            return (full_name[:1], full_name[1:])
        return (full_name, full_name)
