from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_log import ContactLog
from app.repositories.contact_log_repo import ContactLogRepository


class ContactLogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactLogRepository(session)

    async def get_kpis(self) -> dict:
        channel_counts = await self.repo.get_channel_counts()
        return {
            "phone_calls": channel_counts.get("phone_call", 0),
            "live_chats": channel_counts.get("live_chat", 0),
            "emails_sent": channel_counts.get("email", 0),
        }

    async def list_recent(self, page: int = 1, page_size: int = 50) -> dict:
        offset = (page - 1) * page_size
        logs, total = await self.repo.list_recent(offset=offset, limit=page_size)

        items = []
        for log in logs:
            items.append({
                "id": log.id,
                "user_name": log.user_name,
                "user_role": log.user_role,
                "channel": log.channel,
                "description": log.description,
                "agent_name": log.agent_name,
                "duration_seconds": log.duration_seconds,
                "outcome": log.outcome,
                "created_at": log.created_at,
            })

        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def create_log(
        self,
        user_id: UUID,
        user_name: str,
        user_role: str,
        channel: str,
        description: str,
        agent_id: UUID,
        agent_name: str,
        duration_seconds: int | None,
        outcome: str,
    ) -> ContactLog:
        contact_number = await self.repo.get_next_contact_number()
        log = ContactLog(
            contact_number=contact_number,
            user_id=user_id,
            user_name=user_name,
            user_role=user_role,
            channel=channel,
            description=description,
            agent_id=agent_id,
            agent_name=agent_name,
            duration_seconds=duration_seconds,
            outcome=outcome,
        )
        return await self.repo.create(log)
