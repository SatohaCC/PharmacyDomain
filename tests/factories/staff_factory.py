"""スタッフテストで共有する組み立てヘルパー。"""

from __future__ import annotations

from app.domain.corporate import CorporateId
from app.domain.shared.person_name import PersonNames
from app.domain.staff import (
    JobTitle,
    Staff,
    StaffCode,
    StaffQualifications,
)


def create_person_names(
    last_name: str = "山田",
    first_name: str = "太郎",
    last_name_kana: str = "ヤマダ",
    first_name_kana: str = "タロウ",
) -> PersonNames:
    return PersonNames.create(
        last_name=last_name,
        first_name=first_name,
        last_name_kana=last_name_kana,
        first_name_kana=first_name_kana,
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
    return Staff.create(
        corporate_id=corporate_id
        if corporate_id is not None
        else CorporateId.generate(),
        names=create_person_names(
            last_name=last_name,
            first_name=first_name,
            last_name_kana=last_name_kana,
            first_name_kana=first_name_kana,
        ),
        qualifications=qualifications,
        job_title=JobTitle(job_title) if job_title else None,
        code=StaffCode(code) if code else None,
    )
