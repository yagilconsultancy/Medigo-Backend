import logging
import time
import uuid
from dataclasses import dataclass

import httpx

from mediride_common.exceptions import ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30.0

SANDBOX_BASE_URL = "https://api.sb.moneris.io"
PRODUCTION_BASE_URL = "https://api.moneris.io"


@dataclass
class MonerisTokenResponse:
    access_token: str
    expires_in: int
    token_type: str
    obtained_at: float  # time.time()

    @property
    def is_expired(self) -> bool:
        # Refresh 60 seconds before actual expiry
        return time.time() >= (self.obtained_at + self.expires_in - 60)


@dataclass
class MonerisPaymentResult:
    success: bool
    transaction_id: str | None = None
    reference_number: str | None = None
    response_code: str | None = None
    message: str | None = None
    raw_response: dict | None = None


@dataclass
class MonerisVaultResult:
    success: bool
    data_key: str | None = None
    message: str | None = None
    raw_response: dict | None = None


class MonerisClient:
    """Async HTTP client for the Moneris REST API.

    Supports:
    - OAuth2 client_credentials authentication
    - Card tokenization (Vault)
    - Purchase / Pre-auth / Capture
    - Refunds
    - Vault-based (card-on-file) purchases for payouts
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        store_id: str,
        *,
        sandbox: bool = True,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._store_id = store_id
        self._base_url = SANDBOX_BASE_URL if sandbox else PRODUCTION_BASE_URL
        self._token: MonerisTokenResponse | None = None

    async def _get_access_token(self) -> str:
        """Obtain or refresh OAuth2 access token via client_credentials grant."""
        if self._token and not self._token.is_expired:
            return self._token.access_token

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": "payment.write payment.read",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if response.status_code != 200:
                logger.error(
                    f"Moneris OAuth2 token request failed: {response.status_code} {response.text}"
                )
                raise ServiceUnavailableError("Failed to authenticate with Moneris")

            data = response.json()
            self._token = MonerisTokenResponse(
                access_token=data["access_token"],
                expires_in=int(data.get("expires_in", 3600)),
                token_type=data.get("token_type", "Bearer"),
                obtained_at=time.time(),
            )
            logger.info("Moneris OAuth2 token obtained successfully")
            return self._token.access_token

        except httpx.RequestError as e:
            logger.error(f"Moneris OAuth2 connection error: {e}")
            raise ServiceUnavailableError("Cannot connect to Moneris")

    async def _request(
        self, method: str, path: str, json_body: dict | None = None
    ) -> dict:
        """Make an authenticated request to the Moneris REST API."""
        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=headers,
                    json=json_body,
                )
        except httpx.RequestError as e:
            logger.error(f"Moneris API request error: {e}")
            raise ServiceUnavailableError("Cannot connect to Moneris")

        if response.status_code == 401:
            # Token may have expired server-side; clear and retry once
            self._token = None
            token = await self._get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    response = await client.request(
                        method,
                        f"{self._base_url}{path}",
                        headers=headers,
                        json=json_body,
                    )
            except httpx.RequestError as e:
                logger.error(f"Moneris API retry request error: {e}")
                raise ServiceUnavailableError("Cannot connect to Moneris")

        return response.json()

    # ------------------------------------------------------------------ #
    # Vault (Tokenization)
    # ------------------------------------------------------------------ #

    async def tokenize_card(
        self,
        card_number: str,
        expiry_month: str,
        expiry_year: str,
        holder_name: str,
        *,
        cvd: str | None = None,
        avs_street: str | None = None,
        avs_zipcode: str | None = None,
    ) -> MonerisVaultResult:
        """Tokenize a card and store it in Moneris Vault.

        Returns a data_key (permanent token) for future transactions.
        """
        payload: dict = {
            "store_id": self._store_id,
            "type": "res_add_cc",
            "crypt_type": "7",
            "pan": card_number,
            "expdate": f"{expiry_year[-2:]}{expiry_month.zfill(2)}",
            "cust_id": str(uuid.uuid4())[:20],
            "holder_name": holder_name,
        }

        if cvd:
            payload["cvd_info"] = {"cvd_indicator": "1", "cvd_value": cvd}
        if avs_street and avs_zipcode:
            payload["avs_info"] = {
                "avs_street_number": avs_street,
                "avs_zipcode": avs_zipcode,
            }

        try:
            data = await self._request("POST", "/v1/vault/profiles", payload)

            response_code = data.get("response_code", "")
            success = response_code == "001" or data.get("complete") == "true"

            return MonerisVaultResult(
                success=success,
                data_key=data.get("data_key") if success else None,
                message=data.get("message", ""),
                raw_response=data,
            )
        except Exception as e:
            logger.error(f"Moneris tokenization failed: {e}")
            return MonerisVaultResult(
                success=False, message=str(e)
            )

    async def delete_vault_profile(self, data_key: str) -> bool:
        """Remove a card profile from Moneris Vault."""
        payload = {
            "store_id": self._store_id,
            "type": "res_delete",
            "data_key": data_key,
        }
        try:
            data = await self._request("DELETE", f"/v1/vault/profiles/{data_key}", payload)
            return data.get("complete") == "true"
        except Exception as e:
            logger.error(f"Moneris vault delete failed: {e}")
            return False

    # ------------------------------------------------------------------ #
    # Payments
    # ------------------------------------------------------------------ #

    async def purchase(
        self,
        order_id: str,
        amount: float,
        *,
        data_key: str | None = None,
        card_number: str | None = None,
        expiry_month: str | None = None,
        expiry_year: str | None = None,
        cvd: str | None = None,
        description: str | None = None,
    ) -> MonerisPaymentResult:
        """Process a purchase transaction.

        Uses vault token (data_key) or raw card details.
        """
        amount_str = f"{amount:.2f}"

        if data_key:
            payload: dict = {
                "store_id": self._store_id,
                "type": "res_purchase_cc",
                "data_key": data_key,
                "order_id": order_id,
                "amount": amount_str,
                "crypt_type": "7",
            }
        elif card_number and expiry_month and expiry_year:
            payload = {
                "store_id": self._store_id,
                "type": "purchase",
                "order_id": order_id,
                "amount": amount_str,
                "pan": card_number,
                "expdate": f"{expiry_year[-2:]}{expiry_month.zfill(2)}",
                "crypt_type": "7",
            }
            if cvd:
                payload["cvd_info"] = {"cvd_indicator": "1", "cvd_value": cvd}
        else:
            raise ValidationError(
                "Either data_key (vault token) or card details required"
            )

        if description:
            payload["dynamic_descriptor"] = description[:22]

        return await self._process_payment(payload)

    async def preauth(
        self,
        order_id: str,
        amount: float,
        *,
        data_key: str,
    ) -> MonerisPaymentResult:
        """Pre-authorize an amount using a vault token."""
        payload = {
            "store_id": self._store_id,
            "type": "res_preauth_cc",
            "data_key": data_key,
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "crypt_type": "7",
        }
        return await self._process_payment(payload)

    async def capture(
        self,
        order_id: str,
        transaction_id: str,
        amount: float,
    ) -> MonerisPaymentResult:
        """Capture a previously pre-authorized transaction."""
        payload = {
            "store_id": self._store_id,
            "type": "completion",
            "order_id": order_id,
            "comp_amount": f"{amount:.2f}",
            "txn_number": transaction_id,
            "crypt_type": "7",
        }
        return await self._process_payment(payload)

    async def refund(
        self,
        order_id: str,
        transaction_id: str,
        amount: float,
    ) -> MonerisPaymentResult:
        """Refund a completed transaction."""
        payload = {
            "store_id": self._store_id,
            "type": "refund",
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "txn_number": transaction_id,
            "crypt_type": "7",
        }
        return await self._process_payment(payload)

    async def void(
        self,
        order_id: str,
        transaction_id: str,
    ) -> MonerisPaymentResult:
        """Void/cancel an unsettled transaction."""
        payload = {
            "store_id": self._store_id,
            "type": "purchasecorrection",
            "order_id": order_id,
            "txn_number": transaction_id,
            "crypt_type": "7",
        }
        return await self._process_payment(payload)

    async def _process_payment(self, payload: dict) -> MonerisPaymentResult:
        """Send a payment request and parse the response."""
        try:
            data = await self._request("POST", "/v1/payments", payload)

            response_code = data.get("response_code", "999")
            # Moneris: response codes < 50 indicate approval
            try:
                is_approved = int(response_code) < 50
            except (ValueError, TypeError):
                is_approved = False

            return MonerisPaymentResult(
                success=is_approved,
                transaction_id=data.get("txn_number"),
                reference_number=data.get("reference_number"),
                response_code=response_code,
                message=data.get("message", ""),
                raw_response=data,
            )

        except ServiceUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Moneris payment processing error: {e}")
            return MonerisPaymentResult(
                success=False,
                message=str(e),
            )

    # ------------------------------------------------------------------ #
    # Payout / Fund Transfer (for driver withdrawals)
    # ------------------------------------------------------------------ #

    async def process_payout(
        self,
        order_id: str,
        amount: float,
        data_key: str,
    ) -> MonerisPaymentResult:
        """Process a payout/credit to a driver's card on file.

        Uses Moneris Vault independent refund (credit) to push funds
        to the card associated with the data_key.
        """
        payload = {
            "store_id": self._store_id,
            "type": "res_ind_refund_cc",
            "data_key": data_key,
            "order_id": order_id,
            "amount": f"{amount:.2f}",
            "crypt_type": "7",
        }
        return await self._process_payment(payload)
