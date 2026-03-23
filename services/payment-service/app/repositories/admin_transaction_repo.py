from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fare_breakdown import FareBreakdown
from app.models.payment_method import PaymentMethod
from app.models.transaction import Transaction


_STATUS_MAP = {
    "completed": ["completed"],
    "pending": ["pending", "processing"],
    "failed": ["failed"],
}


class AdminTransactionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_transaction_kpis(self) -> dict:
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.coalesce(
                    func.sum(
                        func.case(
                            (Transaction.status == "completed", Transaction.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_collected"),
                func.count()
                .filter(Transaction.transaction_type == "refund")
                .label("refund_count"),
                func.count()
                .filter(Transaction.status.in_(["pending", "processing"]))
                .label("pending_count"),
            ).where(Transaction.transaction_type != "withdrawal")
        )
        row = result.one()
        return {
            "total_transactions": row.total,
            "total_collected": float(row.total_collected),
            "refund_count": row.refund_count,
            "pending_count": row.pending_count,
        }

    async def get_payment_method_breakdown(self) -> list[dict]:
        result = await self.session.execute(
            select(
                PaymentMethod.method_type,
                func.count().label("count"),
                func.coalesce(func.sum(Transaction.amount), 0).label("amount"),
            )
            .join(PaymentMethod, PaymentMethod.user_id == Transaction.user_id)
            .where(
                Transaction.transaction_type == "ride_payment",
                Transaction.status == "completed",
                PaymentMethod.is_default.is_(True),
                PaymentMethod.deleted_at.is_(None),
            )
            .group_by(PaymentMethod.method_type)
            .order_by(func.sum(Transaction.amount).desc())
        )

        display_names = {
            "credit_card": "Credit/Debit Card",
            "debit_card": "Debit Card",
            "bank_account": "Direct Pay",
        }

        return [
            {
                "method_type": row.method_type,
                "display_name": display_names.get(row.method_type, row.method_type.replace("_", " ").title()),
                "amount": float(row.amount),
                "count": row.count,
            }
            for row in result.all()
        ]

    async def get_all_transactions(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Transaction], int]:
        conditions = [Transaction.transaction_type != "withdrawal"]

        if status_filter and status_filter in _STATUS_MAP:
            conditions.append(Transaction.status.in_(_STATUS_MAP[status_filter]))

        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Transaction.id.cast(str).ilike(pattern),
                    Transaction.reference_id.ilike(pattern),
                    Transaction.description.ilike(pattern),
                )
            )

        base_query = select(Transaction).where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Transaction.created_at.desc())
        )
        return list(result.scalars().all()), total
