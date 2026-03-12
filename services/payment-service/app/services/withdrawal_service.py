import logging
from uuid import UUID

from app.clients.stripe_client import StripeClient
from app.config import settings
from app.models.withdrawal import Withdrawal
from app.repositories.earnings_repo import EarningsRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.repositories.withdrawal_repo import WithdrawalRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import WithdrawalPayload
from mediride_common.exceptions import NotFoundError, ValidationError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class WithdrawalService:
    def __init__(
        self,
        withdrawal_repo: WithdrawalRepository,
        earnings_repo: EarningsRepository,
        payment_method_repo: PaymentMethodRepository,
        publisher: EventPublisher,
        stripe_client: StripeClient,
    ):
        self.withdrawal_repo = withdrawal_repo
        self.earnings_repo = earnings_repo
        self.payment_method_repo = payment_method_repo
        self.publisher = publisher
        self.stripe = stripe_client

    async def get_withdrawal_fee(self, amount: float) -> dict:
        fee = round(amount * settings.WITHDRAWAL_FEE_PERCENT, 2)
        return {
            "amount": amount,
            "transaction_fee": fee,
            "net_amount": round(amount - fee, 2),
        }

    async def request_withdrawal(
        self, driver_id: UUID, amount: float, payment_method_id: UUID
    ) -> Withdrawal:
        if amount < settings.MIN_WITHDRAWAL_AMOUNT:
            raise ValidationError(
                f"Minimum withdrawal amount is ${settings.MIN_WITHDRAWAL_AMOUNT}"
            )

        earnings = await self.earnings_repo.get_or_create(driver_id)
        if float(earnings.available_balance) < amount:
            raise ValidationError(
                f"Insufficient balance. Available: ${float(earnings.available_balance)}"
            )

        pm = await self.payment_method_repo.get_by_id(payment_method_id)
        if not pm or pm.user_id != driver_id:
            raise NotFoundError("Payment method not found")

        if not pm.external_id:
            raise ValidationError(
                "Payment method is not linked to Stripe. Please re-add your card."
            )

        fee_info = await self.get_withdrawal_fee(amount)

        withdrawal = Withdrawal(
            driver_id=driver_id,
            amount=amount,
            transaction_fee=fee_info["transaction_fee"],
            net_amount=fee_info["net_amount"],
            payment_method_id=payment_method_id,
        )
        withdrawal = await self.withdrawal_repo.create(withdrawal)

        # Deduct from available balance
        await self.earnings_repo.deduct_for_withdrawal(driver_id, amount)

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.WITHDRAWAL_REQUESTED,
            WithdrawalPayload(
                withdrawal_id=withdrawal.id,
                driver_id=driver_id,
                amount=amount,
                status="pending",
            ).model_dump(mode="json"),
        )

        logger.info(f"Withdrawal ${amount} requested by driver {driver_id}")
        return withdrawal

    async def process_withdrawal(self, withdrawal_id: UUID) -> Withdrawal:
        """Process a withdrawal via Stripe payout. Called by background task."""
        withdrawal = await self.withdrawal_repo.get_by_id(withdrawal_id)
        if not withdrawal:
            raise NotFoundError("Withdrawal not found")

        # Fetch the payment method for the Stripe PaymentMethod ID
        pm = await self.payment_method_repo.get_by_id(withdrawal.payment_method_id)
        if not pm or not pm.external_id:
            await self._fail_withdrawal(
                withdrawal_id,
                withdrawal.driver_id,
                float(withdrawal.amount),
                "Payment method missing or not tokenized",
            )
            return await self.withdrawal_repo.get_by_id(withdrawal_id)

        try:
            # Process payout via Stripe Transfer
            order_id = f"WD-{withdrawal_id}"
            result = await self.stripe.process_payout(
                order_id=order_id,
                amount=float(withdrawal.net_amount),
                data_key=pm.external_id,
                connected_account_id=pm.stripe_customer_id,
            )

            if not result.success:
                await self._fail_withdrawal(
                    withdrawal_id,
                    withdrawal.driver_id,
                    float(withdrawal.amount),
                    f"Stripe payout failed: {result.message}",
                )
                return await self.withdrawal_repo.get_by_id(withdrawal_id)

            # Payout succeeded
            await self.withdrawal_repo.update(
                withdrawal_id,
                status="completed",
                processed_at=utc_now(),
            )
            await self.earnings_repo.complete_withdrawal(
                withdrawal.driver_id, float(withdrawal.amount)
            )

            logger.info(
                f"Withdrawal {withdrawal_id} completed via Stripe "
                f"(txn: {result.transaction_id})"
            )

            await self.publisher.publish(
                Exchanges.PAYMENTS,
                RoutingKeys.WITHDRAWAL_COMPLETED,
                WithdrawalPayload(
                    withdrawal_id=withdrawal_id,
                    driver_id=withdrawal.driver_id,
                    amount=float(withdrawal.amount),
                    status="completed",
                ).model_dump(mode="json"),
            )

        except Exception as e:
            logger.error(f"Withdrawal {withdrawal_id} failed: {e}")
            await self._fail_withdrawal(
                withdrawal_id,
                withdrawal.driver_id,
                float(withdrawal.amount),
                str(e),
            )

        return await self.withdrawal_repo.get_by_id(withdrawal_id)

    async def _fail_withdrawal(
        self,
        withdrawal_id: UUID,
        driver_id: UUID,
        amount: float,
        reason: str,
    ) -> None:
        """Mark withdrawal as failed and reverse the balance deduction."""
        logger.error(f"Withdrawal {withdrawal_id} failed: {reason}")
        await self.withdrawal_repo.update(
            withdrawal_id, status="failed", failure_reason=reason
        )
        # Reverse the balance deduction so funds are available again
        await self.earnings_repo.reverse_withdrawal_deduction(driver_id, amount)

        await self.publisher.publish(
            Exchanges.PAYMENTS,
            RoutingKeys.WITHDRAWAL_FAILED,
            WithdrawalPayload(
                withdrawal_id=withdrawal_id,
                driver_id=driver_id,
                amount=amount,
                status="failed",
            ).model_dump(mode="json"),
        )

    async def get_withdrawal_history(
        self, driver_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[Withdrawal], int]:
        return await self.withdrawal_repo.get_by_driver(driver_id, offset, limit)
