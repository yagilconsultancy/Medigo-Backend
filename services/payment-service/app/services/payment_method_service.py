import logging
from uuid import UUID

from app.clients.stripe_client import StripeClient
from app.models.payment_method import PaymentMethod
from app.repositories.payment_method_repo import PaymentMethodRepository
from mediride_common.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class PaymentMethodService:
    def __init__(
        self,
        pm_repo: PaymentMethodRepository,
        stripe_client: StripeClient,
    ):
        self.pm_repo = pm_repo
        self.stripe = stripe_client

    async def add_payment_method(
        self,
        user_id: UUID,
        method_type: str,
        card_number: str,
        expiry_month: str,
        expiry_year: str,
        holder_name: str,
        *,
        cvd: str | None = None,
    ) -> PaymentMethod:
        """Tokenize card via Stripe and store the PaymentMethod ID locally."""
        # Look up existing Stripe customer_id for this user
        existing = await self.pm_repo.get_by_user(user_id)
        existing_customer_id = None
        for m in existing:
            if m.stripe_customer_id:
                existing_customer_id = m.stripe_customer_id
                break

        vault_result = await self.stripe.tokenize_card(
            card_number=card_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            holder_name=holder_name,
            cvd=cvd,
            user_id=str(user_id),
            existing_customer_id=existing_customer_id,
        )

        if not vault_result.success or not vault_result.data_key:
            logger.error(
                f"Stripe tokenization failed for user {user_id}: {vault_result.message}"
            )
            raise ValidationError(
                f"Card tokenization failed: {vault_result.message or 'Unknown error'}"
            )

        last_four = card_number[-4:]
        brand = _detect_card_brand(card_number)

        # First payment method becomes the default
        is_default = len(existing) == 0

        method = PaymentMethod(
            user_id=user_id,
            method_type=method_type,
            last_four=last_four,
            brand=brand,
            holder_name=holder_name,
            is_default=is_default,
            external_id=vault_result.data_key,
            stripe_customer_id=vault_result.customer_id,
        )
        return await self.pm_repo.create(method)

    async def list_payment_methods(self, user_id: UUID) -> list[PaymentMethod]:
        return await self.pm_repo.get_by_user(user_id)

    async def set_default_method(self, user_id: UUID, pm_id: UUID) -> PaymentMethod:
        pm = await self.pm_repo.get_by_id(pm_id)
        if not pm or pm.user_id != user_id:
            raise NotFoundError("Payment method not found")
        await self.pm_repo.set_default(user_id, pm_id)
        return await self.pm_repo.get_by_id(pm_id)

    async def remove_payment_method(self, user_id: UUID, pm_id: UUID) -> None:
        pm = await self.pm_repo.get_by_id(pm_id)
        if not pm or pm.user_id != user_id:
            raise NotFoundError("Payment method not found")
        if pm.is_default:
            raise ValidationError(
                "Cannot remove default payment method. Set another as default first."
            )

        # Detach from Stripe
        if pm.external_id:
            deleted = await self.stripe.delete_vault_profile(pm.external_id)
            if not deleted:
                logger.warning(
                    f"Failed to detach Stripe PaymentMethod {pm.external_id} for user {user_id}"
                )

        await self.pm_repo.soft_delete(pm_id)


def _detect_card_brand(card_number: str) -> str:
    """Detect card brand from the card number prefix."""
    if card_number.startswith("4"):
        return "Visa"
    if card_number[:2] in ("51", "52", "53", "54", "55"):
        return "Mastercard"
    if card_number[:2] in ("34", "37"):
        return "Amex"
    if card_number[:4] == "6011" or card_number[:2] == "65":
        return "Discover"
    return "Unknown"
