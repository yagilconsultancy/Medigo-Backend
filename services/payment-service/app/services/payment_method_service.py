import logging
from uuid import UUID

from app.clients.moneris_client import MonerisClient
from app.models.payment_method import PaymentMethod
from app.repositories.payment_method_repo import PaymentMethodRepository
from mediride_common.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class PaymentMethodService:
    def __init__(
        self,
        pm_repo: PaymentMethodRepository,
        moneris_client: MonerisClient,
    ):
        self.pm_repo = pm_repo
        self.moneris = moneris_client

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
        """Tokenize card via Moneris Vault and store the token locally."""
        vault_result = await self.moneris.tokenize_card(
            card_number=card_number,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            holder_name=holder_name,
            cvd=cvd,
        )

        if not vault_result.success or not vault_result.data_key:
            logger.error(
                f"Moneris tokenization failed for user {user_id}: {vault_result.message}"
            )
            raise ValidationError(
                f"Card tokenization failed: {vault_result.message or 'Unknown error'}"
            )

        last_four = card_number[-4:]
        brand = _detect_card_brand(card_number)

        # First payment method becomes the default
        existing = await self.pm_repo.get_by_user(user_id)
        is_default = len(existing) == 0

        method = PaymentMethod(
            user_id=user_id,
            method_type=method_type,
            last_four=last_four,
            brand=brand,
            holder_name=holder_name,
            is_default=is_default,
            external_id=vault_result.data_key,
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

        # Remove from Moneris Vault
        if pm.external_id:
            deleted = await self.moneris.delete_vault_profile(pm.external_id)
            if not deleted:
                logger.warning(
                    f"Failed to delete Moneris vault profile {pm.external_id} for user {user_id}"
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
