"""本人指定の招待の保存。秘密はダイジェストだけ保持する。"""

from sqlalchemy import select

from app.domain.identity.invitation import InvitationDigest, UserInvitation
from app.domain.identity.primitives import UserInvitationId
from app.domain.identity.repository import UserInvitationRepository
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import user_invitations

INVITATION_MAPPING = AggregateMapping(
    table=user_invitations,
    aggregate_type=UserInvitation,
    label="招待",
    search_columns=lambda item: {
        "id": item.id.value,
        "person_id": item.person_id.value,
        "corporate_id": item.corporate_id.value,
        "status": item.status.value,
        "secret_digest": item.secret_digest.value,
        "expires_at": item.expires_at,
    },
)


class PostgresUserInvitationRepository(
    PostgresRepositoryBase, UserInvitationRepository
):
    """同じ招待の再更新は既存の楽観ロックで拒否する。"""

    async def get(self, invitation_id: UserInvitationId) -> UserInvitation | None:
        return await self.get_by_id(INVITATION_MAPPING, invitation_id)

    async def find_by_digest(self, digest: InvitationDigest) -> UserInvitation | None:
        return await self.find_one(
            INVITATION_MAPPING,
            select(user_invitations).where(
                user_invitations.c.secret_digest == digest.value
            ),
        )

    async def save(self, invitation: UserInvitation) -> None:
        await self.save_aggregate(INVITATION_MAPPING, invitation)
