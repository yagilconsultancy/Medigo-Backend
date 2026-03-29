import asyncio
import logging
import uuid
from datetime import datetime, timezone
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.clients.ride_service_client import RideServiceClient
from app.models.rider_issue import RiderIssue
from app.models.rider_issue_note import RiderIssueNote
from app.repositories.admin_rider_repo import AdminRiderRepository
from app.repositories.rider_issue_repo import RiderIssueRepository
from app.schemas.admin_rider import (
    AddIssueNoteRequest,
    AdminRiderActivityItem,
    AdminRiderActivityKPIs,
    AdminRiderActivityResponse,
    AdminRiderDetailResponse,
    AdminRiderKPIs,
    AdminRiderListItem,
    AdminRiderListResponse,
    AdminRiderProfileCard,
    CreateRiderIssueRequest,
    RiderEmergencyContactInfo,
    RiderIssueDetailResponse,
    RiderIssueKPIs,
    RiderIssueListItem,
    RiderIssueListResponse,
    RiderIssueNoteResponse,
    RiderPaymentMethodInfo,
    RiderTripStats,
)
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher

logger = logging.getLogger(__name__)


class AdminRiderService:
    def __init__(
        self,
        repo: AdminRiderRepository,
        issue_repo: RiderIssueRepository,
        ride_client: RideServiceClient,
        payment_client: PaymentServiceClient,
        publisher: EventPublisher,
    ):
        self.repo = repo
        self.issue_repo = issue_repo
        self.ride_client = ride_client
        self.payment_client = payment_client
        self.publisher = publisher

    # --- Helpers ---

    @staticmethod
    def _classify_frequency(trips_7d: int, trips_30d: int) -> str:
        if trips_7d >= 7:
            return "Daily"
        if trips_7d >= 4:
            return "3-4x/week"
        if trips_7d >= 2:
            return "2x/week"
        if trips_7d >= 1:
            return "Weekly"
        if trips_30d > 0:
            return "Irregular"
        return "Inactive"

    @staticmethod
    def _classify_trend(current_month: int, prev_month: int) -> str:
        if current_month > prev_month + 1:
            return "Increasing"
        if current_month < prev_month - 1:
            return "Decreasing"
        return "Stable"

    # --- All Riders ---

    async def list_riders(
        self,
        search: str | None = None,
        status: str | None = None,
        sort_by: str = "created_at",
        page: int = 1,
        limit: int = 20,
    ) -> AdminRiderListResponse:
        offset = (page - 1) * limit

        # Get KPIs and riders in sequence (same DB session)
        kpis_data = await self.repo.get_rider_kpis()
        riders_data, total = await self.repo.list_riders_for_admin(
            search=search, status=status, sort_by=sort_by, offset=offset, limit=limit
        )

        # Get open ticket counts
        rider_ids = [r["user_id"] for r in riders_data]
        ticket_counts = await self.issue_repo.count_open_batch(rider_ids) if rider_ids else {}

        # Get batch activity from ride-service for frequency
        activity_data = await self.ride_client.get_batch_rider_activity(rider_ids) if rider_ids else {}
        activity_data = activity_data or {}

        total_open_tickets = sum(ticket_counts.values())

        riders = []
        for r in riders_data:
            rid_str = str(r["user_id"])
            activity = activity_data.get(rid_str, {})
            trips_7d = activity.get("trips_last_7d", 0)
            trips_30d = activity.get("trips_last_30d", 0)
            total_trips = activity.get("trips_current_month", 0) + activity.get("trips_prev_month", 0)

            riders.append(AdminRiderListItem(
                user_id=r["user_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                email=r.get("email"),
                phone=r.get("phone"),
                avatar_url=r.get("avatar_url"),
                joined_at=r.get("joined_at"),
                total_trips=total_trips,
                total_spent=0.0,
                frequency=self._classify_frequency(trips_7d, trips_30d),
                open_tickets=ticket_counts.get(r["user_id"], 0),
                status=r["status"],
            ))

        return AdminRiderListResponse(
            kpis=AdminRiderKPIs(
                total_riders=kpis_data["total_riders"],
                active_count=kpis_data["active_count"],
                suspended_count=kpis_data["suspended_count"],
                open_tickets=total_open_tickets,
            ),
            riders=riders,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit if total > 0 else 0,
        )

    # --- Rider Detail ---

    async def get_rider_detail(self, rider_id: UUID) -> AdminRiderDetailResponse:
        detail = await self.repo.get_rider_detail(rider_id)
        if not detail:
            raise ValueError("Rider not found")

        # Cross-service enrichment in parallel
        ride_stats_task = self.ride_client.get_rider_stats(rider_id)
        payment_methods_task = self.payment_client.get_rider_payment_methods(rider_id)
        ride_stats, payment_methods = await asyncio.gather(
            ride_stats_task, payment_methods_task
        )

        trip_stats = RiderTripStats()
        if ride_stats:
            trip_stats = RiderTripStats(
                total_rides=ride_stats.get("total_trips", 0),
                total_spent=ride_stats.get("total_spent", 0.0),
                avg_cost=ride_stats.get("avg_cost", 0.0),
            )

        ec_list = [
            RiderEmergencyContactInfo(**ec)
            for ec in detail.get("emergency_contacts", [])
        ]

        pm_list = [
            RiderPaymentMethodInfo(
                brand=pm.get("brand"),
                last_four=pm.get("last_four"),
                is_default=pm.get("is_default", False),
            )
            for pm in (payment_methods or [])
        ]

        return AdminRiderDetailResponse(
            user_id=detail["user_id"],
            first_name=detail["first_name"],
            last_name=detail["last_name"],
            email=detail.get("email"),
            phone=detail.get("phone"),
            avatar_url=detail.get("avatar_url"),
            date_of_birth=detail.get("date_of_birth"),
            gender=detail.get("gender"),
            home_address=detail.get("home_address"),
            medical_notes=detail.get("medical_notes"),
            insurance_provider=detail.get("insurance_provider"),
            insurance_policy_number=detail.get("insurance_policy_number"),
            status=detail["status"],
            suspension_reason=detail.get("suspension_reason"),
            suspended_at=detail.get("suspended_at"),
            created_at=detail.get("created_at"),
            trip_stats=trip_stats,
            emergency_contacts=ec_list,
            payment_methods=pm_list,
        )

    # --- Suspend / Reinstate ---

    async def suspend_rider(
        self, rider_id: UUID, reason: str, admin_id: UUID
    ) -> AdminRiderDetailResponse:
        detail = await self.repo.get_rider_detail(rider_id)
        if not detail:
            raise ValueError("Rider not found")
        if detail["status"] == "suspended":
            raise ValueError("Rider is already suspended")

        await self.repo.suspend_rider(rider_id, reason, admin_id)

        await self.publisher.publish(
            exchange=Exchanges.USERS,
            routing_key=RoutingKeys.RIDER_SUSPENDED,
            payload={
                "rider_id": str(rider_id),
                "reason": reason,
                "suspended_by": str(admin_id),
            },
        )

        return await self.get_rider_detail(rider_id)

    async def reinstate_rider(
        self, rider_id: UUID, admin_id: UUID
    ) -> AdminRiderDetailResponse:
        detail = await self.repo.get_rider_detail(rider_id)
        if not detail:
            raise ValueError("Rider not found")
        if detail["status"] != "suspended":
            raise ValueError("Rider is not suspended")

        await self.repo.reinstate_rider(rider_id)

        await self.publisher.publish(
            exchange=Exchanges.USERS,
            routing_key=RoutingKeys.RIDER_REINSTATED,
            payload={
                "rider_id": str(rider_id),
                "reinstated_by": str(admin_id),
            },
        )

        return await self.get_rider_detail(rider_id)

    # --- Rider Profiles ---

    async def get_rider_profiles(
        self,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[AdminRiderProfileCard], int]:
        offset = (page - 1) * limit
        riders_data, total = await self.repo.get_rider_ids(offset, limit)

        if not riders_data:
            return [], total

        rider_ids = [r["user_id"] for r in riders_data]

        # Parallel cross-service calls
        activity_task = self.ride_client.get_batch_rider_activity(rider_ids)
        activity_data = await activity_task
        activity_data = activity_data or {}

        profiles = []
        for r in riders_data:
            rid_str = str(r["user_id"])
            activity = activity_data.get(rid_str, {})
            total_rides = activity.get("trips_current_month", 0) + activity.get("trips_prev_month", 0)
            last_ride_str = activity.get("last_ride_date")
            last_ride = datetime.fromisoformat(last_ride_str) if last_ride_str else None

            profiles.append(AdminRiderProfileCard(
                user_id=r["user_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                avatar_url=r.get("avatar_url"),
                date_of_birth=r.get("date_of_birth"),
                member_since=r.get("member_since"),
                total_rides=total_rides,
                email=r.get("email"),
                phone=r.get("phone"),
                last_ride=last_ride,
                insurance_provider=r.get("insurance_provider"),
                insurance_policy_number=r.get("insurance_policy_number"),
                emergency_contact_name=r.get("emergency_contact_name"),
                emergency_contact_relationship=r.get("emergency_contact_relationship"),
                payment_brand=None,
                payment_last_four=None,
            ))

        return profiles, total

    # --- Rider Activity ---

    async def get_rider_activity(
        self, page: int = 1, limit: int = 20
    ) -> AdminRiderActivityResponse:
        offset = (page - 1) * limit
        riders_data, total = await self.repo.get_rider_ids(offset, limit)

        if not riders_data:
            return AdminRiderActivityResponse(
                kpis=AdminRiderActivityKPIs(
                    daily_active_riders=0, avg_trips_per_week=0.0, inactive_30_days=0
                ),
                riders=[],
                total=0,
                page=page,
                limit=limit,
                total_pages=0,
            )

        rider_ids = [r["user_id"] for r in riders_data]
        activity_data = await self.ride_client.get_batch_rider_activity(rider_ids)
        activity_data = activity_data or {}

        daily_active = 0
        inactive_30 = 0
        total_trips_week = 0

        items = []
        for r in riders_data:
            rid_str = str(r["user_id"])
            activity = activity_data.get(rid_str, {})
            trips_7d = activity.get("trips_last_7d", 0)
            trips_30d = activity.get("trips_last_30d", 0)
            trips_cm = activity.get("trips_current_month", 0)
            trips_pm = activity.get("trips_prev_month", 0)
            last_ride_str = activity.get("last_ride_date")
            last_seen = datetime.fromisoformat(last_ride_str) if last_ride_str else None

            frequency = self._classify_frequency(trips_7d, trips_30d)
            trend = self._classify_trend(trips_cm, trips_pm)
            avg_per_week = round(trips_30d / 4.3, 1) if trips_30d > 0 else 0.0

            if trips_7d >= 1:
                daily_active += 1
            if trips_30d == 0:
                inactive_30 += 1

            total_trips_week += trips_7d

            items.append(AdminRiderActivityItem(
                user_id=r["user_id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                avatar_url=r.get("avatar_url"),
                last_seen=last_seen,
                frequency=frequency,
                avg_trips_per_week=avg_per_week,
                monthly_trips=trips_cm,
                trend=trend,
                status=r["status"],
            ))

        rider_count = len(riders_data)
        avg_trips = round(total_trips_week / rider_count, 1) if rider_count > 0 else 0.0

        return AdminRiderActivityResponse(
            kpis=AdminRiderActivityKPIs(
                daily_active_riders=daily_active,
                avg_trips_per_week=avg_trips,
                inactive_30_days=inactive_30,
            ),
            riders=items,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit if total > 0 else 0,
        )

    # --- Rider Ride History ---

    async def get_rider_rides(
        self, rider_id: UUID, page: int = 1, limit: int = 20
    ) -> dict:
        result = await self.ride_client.get_rider_rides(rider_id, page=page, limit=limit)
        return result or {"rides": [], "total": 0}

    # --- Issues ---

    async def create_issue(
        self, admin_id: UUID, data: CreateRiderIssueRequest
    ) -> RiderIssueDetailResponse:
        issue = RiderIssue(
            id=uuid.uuid4(),
            rider_id=data.rider_id,
            issue_type=data.issue_type,
            subject=data.subject,
            description=data.description,
            priority=data.priority,
            created_by=admin_id,
        )
        issue = await self.issue_repo.create(issue)

        await self.publisher.publish(
            exchange=Exchanges.USERS,
            routing_key=RoutingKeys.RIDER_ISSUE_CREATED,
            payload={
                "issue_id": str(issue.id),
                "rider_id": str(data.rider_id),
                "issue_type": data.issue_type,
                "subject": data.subject,
                "priority": data.priority,
            },
        )

        return await self.get_issue_detail(issue.id)

    async def get_issue_detail(self, issue_id: UUID) -> RiderIssueDetailResponse:
        issue = await self.issue_repo.get_by_id(issue_id)
        if not issue:
            raise ValueError("Issue not found")

        rider = issue.rider
        rider_name = f"{rider.first_name} {rider.last_name}" if rider else "Unknown"

        notes = [
            RiderIssueNoteResponse(
                id=n.id,
                author_id=n.author_id,
                note_text=n.note_text,
                action=n.action,
                created_at=n.created_at,
            )
            for n in (issue.notes or [])
        ]

        return RiderIssueDetailResponse(
            id=issue.id,
            ticket_number=f"TKT-{issue.ticket_number}",
            rider_id=issue.rider_id,
            rider_name=rider_name,
            issue_type=issue.issue_type,
            subject=issue.subject,
            description=issue.description,
            status=issue.status,
            priority=issue.priority,
            assigned_to=issue.assigned_to,
            resolved_at=issue.resolved_at,
            created_by=issue.created_by,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            notes=notes,
        )

    async def list_issues(
        self,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> RiderIssueListResponse:
        offset = (page - 1) * limit
        kpis_data = await self.issue_repo.get_issue_kpis()
        issues_data, total = await self.issue_repo.list_issues(
            status=status, priority=priority, search=search, offset=offset, limit=limit
        )

        issues = [RiderIssueListItem(**i) for i in issues_data]

        return RiderIssueListResponse(
            kpis=RiderIssueKPIs(**kpis_data),
            issues=issues,
            total=total,
            page=page,
            limit=limit,
            total_pages=(total + limit - 1) // limit if total > 0 else 0,
        )

    async def update_issue_status(
        self, issue_id: UUID, new_status: str, admin_id: UUID
    ) -> RiderIssueDetailResponse:
        issue = await self.issue_repo.get_by_id(issue_id)
        if not issue:
            raise ValueError("Issue not found")

        valid_transitions = {
            "open": ["under_review", "resolved"],
            "under_review": ["resolved", "open"],
            "resolved": ["open"],
        }
        allowed = valid_transitions.get(issue.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{issue.status}' to '{new_status}'"
            )

        resolved_at = datetime.now(timezone.utc) if new_status == "resolved" else None
        await self.issue_repo.update_status(issue_id, new_status, resolved_at)

        # Add system note
        note = RiderIssueNote(
            id=uuid.uuid4(),
            issue_id=issue_id,
            author_id=admin_id,
            note_text=f"Status changed from '{issue.status}' to '{new_status}'",
            action="status_change",
        )
        await self.issue_repo.add_note(note)

        await self.publisher.publish(
            exchange=Exchanges.USERS,
            routing_key=RoutingKeys.RIDER_ISSUE_STATUS_CHANGED,
            payload={
                "issue_id": str(issue_id),
                "old_status": issue.status,
                "new_status": new_status,
                "changed_by": str(admin_id),
            },
        )

        return await self.get_issue_detail(issue_id)

    async def add_issue_note(
        self, issue_id: UUID, admin_id: UUID, data: AddIssueNoteRequest
    ) -> RiderIssueDetailResponse:
        issue = await self.issue_repo.get_by_id(issue_id)
        if not issue:
            raise ValueError("Issue not found")

        note = RiderIssueNote(
            id=uuid.uuid4(),
            issue_id=issue_id,
            author_id=admin_id,
            note_text=data.note_text,
            action="note",
        )
        await self.issue_repo.add_note(note)

        return await self.get_issue_detail(issue_id)
