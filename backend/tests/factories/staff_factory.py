"""スタッフテストで共有する組み立てヘルパー。"""

from __future__ import annotations

from app.domain.corporate.identifiers import CorporateId
from app.domain.shared.person_name import (
    PersonName,
    PersonNameKana,
    PersonNameKanaPart,
    PersonNamePart,
    PersonNames,
)
from app.domain.staff.entities import Staff
from app.domain.staff.identifiers import StaffId
from app.domain.staff.primitives import JobTitle, StaffCode
from app.domain.staff.value_objects import StaffQualifications


def create_person_names(
    last_name: str = "山田",
    first_name: str = "太郎",
    last_name_kana: str = "ヤマダ",
    first_name_kana: str = "タロウ",
) -> PersonNames:
    return PersonNames(
        kanji=PersonName(
            last_name=PersonNamePart(last_name), first_name=PersonNamePart(first_name)
        ),
        kana=PersonNameKana(
            last_name=PersonNameKanaPart(last_name_kana),
            first_name=PersonNameKanaPart(first_name_kana),
        ),
    )


def create_staff(
    *,
    corporate_id: CorporateId | None = None,
    last_name: str = "山田",
    first_name: str = "太郎",
    last_name_kana: str = "ヤマダ",
    first_name_kana: str = "タロウ",
    qualifications: StaffQualifications | None = None,
    job_title: str | None = None,
    code: str | None = None,
) -> Staff:
    """既定値を持つ Staff を組み立てる（永続化はしない）。"""
    return Staff(
        id=StaffId.generate(),
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        names=create_person_names(
            last_name=last_name,
            first_name=first_name,
            last_name_kana=last_name_kana,
            first_name_kana=first_name_kana,
        ),
        qualifications=qualifications or StaffQualifications.empty(),
        affiliations=(),
        job_title=JobTitle(job_title) if job_title else None,
        code=StaffCode(code) if code else None,
        phone_number=None,
        email=None,
        is_active=True,
    )
