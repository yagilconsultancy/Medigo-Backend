import logging
import secrets
from datetime import timedelta
from uuid import UUID

from app.clients.auth_service_client import AuthServiceClient
from app.config import settings
from app.models.admin_invitation import AdminInvitation
from app.models.admin_role import AdminRole, AdminRoleAssignment
from app.models.user import User
from app.repositories.admin_invitation_repo import AdminInvitationRepository
from app.repositories.admin_role_repo import AdminRoleRepository
from app.repositories.user_repo import UserRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import AdminInviteSentPayload
from mediride_common.exceptions import ConflictError, NotFoundError, ValidationError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class AdminInvitationService:
    def __init__(
        self,
        invitation_repo: AdminInvitationRepository,
        user_repo: UserRepository,
        admin_role_repo: AdminRoleRepository,
        publisher: EventPublisher,
        auth_client: AuthServiceClient,
    ):
        self.invitation_repo = invitation_repo
        self.user_repo = user_repo
        self.admin_role_repo = admin_role_repo
        self.publisher = publisher
        self.auth_client = auth_client

    async def send_invitation(
        self, email: str, full_name: str, role_name: str, invited_by: UUID
    ) -> AdminInvitation:
        """Create admin account and send credentials email."""
        # Validate role exists
        role = await self.admin_role_repo.get_by_name(role_name)
        if not role:
            raise ValidationError(f"Invalid admin role: {role_name}")

        # Check if user already exists with this email
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ConflictError("A user with this email already exists")

        # Check if there's already a pending invitation
        existing_invitation = await self.invitation_repo.get_by_email(email)
        if existing_invitation:
            raise ConflictError("An invitation for this email already exists")

        # Get inviter's name
        inviter = await self.user_repo.get_by_id(invited_by)
        if not inviter:
            raise NotFoundError("Inviter not found")
        inviter_name = f"{inviter.first_name} {inviter.last_name}"

        # Use default admin password
        default_password = settings.DEFAULT_ADMIN_PASSWORD

        # Create credential in auth-service
        try:
            cred_result = await self.auth_client.create_admin_credential(
                email=email,
                password=default_password,
            )
        except RuntimeError as e:
            raise ValidationError(str(e))

        user_id = UUID(cred_result["user_id"])

        # Split full_name into first/last
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Create user record
        user = User(
            id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role="admin",
            is_active=True,
        )
        await self.user_repo.create(user)

        # Create invitation record (mark as accepted immediately)
        token = secrets.token_urlsafe(32)
        invitation = AdminInvitation(
            email=email,
            full_name=full_name,
            role_name=role_name,
            invited_by=invited_by,
            token=token,
            expires_at=utc_now() + timedelta(days=settings.INVITE_TOKEN_EXPIRE_DAYS),
        )
        await self.invitation_repo.create(invitation)

        # Create admin role assignment
        assignment = AdminRoleAssignment(
            user_id=user_id,
            role_id=role.id,
            assigned_by=invited_by,
        )
        await self.admin_role_repo.assign_role(assignment)

        # Mark invitation as accepted
        await self.invitation_repo.mark_accepted(invitation.id)

        # Publish event for notification service to send credentials email
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.ADMIN_INVITE_SENT,
            AdminInviteSentPayload(
                invitation_id=invitation.id,
                email=email,
                full_name=full_name,
                role_display_name=role.display_name,
                temporary_password=default_password,
                invited_by_name=inviter_name,
            ).model_dump(mode="json"),
        )

        logger.info(f"Admin account created and credentials sent: {email} with role {role_name}")
        return invitation

    async def list_pending_invitations(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """List all pending admin invitations with enriched data."""
        invitations, total = await self.invitation_repo.list_pending(offset, limit)

        # Enrich with role display names and inviter names
        enriched = []
        for invitation in invitations:
            role = await self.admin_role_repo.get_by_name(invitation.role_name)
            inviter = await self.user_repo.get_by_id(invitation.invited_by)

            enriched.append(
                {
                    "id": invitation.id,
                    "email": invitation.email,
                    "full_name": invitation.full_name,
                    "role_name": invitation.role_name,
                    "role_display_name": role.display_name if role else invitation.role_name,
                    "invited_by_name": (
                        f"{inviter.first_name} {inviter.last_name}"
                        if inviter
                        else "Unknown"
                    ),
                    "status": invitation.status,
                    "expires_at": invitation.expires_at,
                    "created_at": invitation.created_at,
                    "accepted_at": invitation.accepted_at,
                }
            )

        return enriched, total

    async def revoke_invitation(self, invitation_id: UUID) -> None:
        """Revoke a pending invitation."""
        invitation = await self.invitation_repo.get_by_id(invitation_id)
        if not invitation:
            raise NotFoundError("Invitation not found")

        await self.invitation_repo.revoke(invitation_id)
        logger.info(f"Admin invitation revoked: {invitation.email}")
