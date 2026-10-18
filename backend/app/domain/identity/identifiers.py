"""identityの公開識別子。"""

from __future__ import annotations

from app.domain.foundation.primitives.identifiers import EntityUUID


class CorporateMembershipId(EntityUUID):
    """法人アクセス権の識別子。"""

    identifier_name = "法人アクセス権ID"


class UserInvitationId(EntityUUID):
    """本人を指定した招待の識別子。"""

    identifier_name = "招待ID"
