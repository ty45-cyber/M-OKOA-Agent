"""
Daraja Service — M-Pesa API client for M-Okoa Agent.
Handles: OAuth token management, STK Push, C2B, B2C, Account Balance, Transaction Status.

All Daraja credentials are decrypted at call time — never held in memory longer than needed.
Token refresh is handled automatically via Redis cache.
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.core.redis_client import RedisKeys, get_redis
from app.core.security import decrypt_field

logger = structlog.get_logger(__name__)
settings = get_settings()

# ── Daraja response result codes ─────────────────────────────
DARAJA_SUCCESS_CODE = "0"
STK_PUSH_SUCCESS_CODE = "0"


class DarajaError(Exception):
    """Raised when Daraja returns a non-success response."""

    def __init__(self, message: str, result_code: str | None = None, raw: dict | None = None):
        super().__init__(message)
        self.result_code = result_code
        self.raw = raw or {}


class DarajaTillCredentials:
    """
    Decrypted Daraja credentials for a single till.
    Constructed at call time, not stored as class state.
    """

    __slots__ = (
        "consumer_key",
        "consumer_secret",
        "shortcode",
        "passkey",
    )

    def __init__(
        self,
        encrypted_consumer_key: str,
        encrypted_consumer_secret: str,
        shortcode: str,
        encrypted_passkey: str,
    ) -> None:
        self.consumer_key = decrypt_field(encrypted_consumer_key)
        self.consumer_secret = decrypt_field(encrypted_consumer_secret)
        self.shortcode = shortcode
        self.passkey = decrypt_field(encrypted_passkey)


class DarajaService:
    """
    Stateless M-Pesa Daraja API client.
    One instance per request — credentials supplied per call.
    """

    def __init__(self) -> None:
        self._base_url = settings.daraja_base_url
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0),
            headers={"Content-Type": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── OAuth Token ──────────────────────────────────────────

    async def _get_access_token(self, creds: DarajaTillCredentials) -> str:
        """
        Fetch or return cached OAuth token for this shortcode.
        Daraja tokens are valid for 1 hour — cached in Redis for 55 minutes.
        """
        redis = get_redis()
        cache_key = RedisKeys.daraja_token(creds.shortcode)

        cached = await redis.get(cache_key)
        if cached:
            return cached

        raw = f"{creds.consumer_key}:{creds.consumer_secret}"
        encoded = base64.b64encode(raw.encode()).decode()

        response = await self._client.get(
            f"{self._base_url}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {encoded}"},
        )
        response.raise_for_status()
        data = response.json()

        token: str = data["access_token"]
        expires_in: int = int(data.get("expires_in", 3600))
        ttl = max(expires_in - 300, 60)  # Expire 5 min early to prevent edge cases

        await redis.setex(cache_key, ttl, token)
        logger.info("daraja.token_refreshed", shortcode=creds.shortcode, ttl=ttl)
        return token

    async def _auth_headers(self, creds: DarajaTillCredentials) -> dict[str, str]:
        token = await self._get_access_token(creds)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── Password generation (STK Push) ───────────────────────

    @staticmethod
    def _generate_stk_password(shortcode: str, passkey: str, timestamp: str) -> str:
        """
        Daraja STK password = Base64(shortcode + passkey + timestamp).
        Timestamp format: YYYYMMDDHHmmss
        """
        raw = f"{shortcode}{passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode()

    @staticmethod
    def _current_timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # ── STK Push (Lipa na M-Pesa Online) ─────────────────────

    async def initiate_stk_push(
        self,
        creds: DarajaTillCredentials,
        phone_number: str,
        amount: Decimal,
        account_reference: str,
        transaction_desc: str,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Trigger an STK Push prompt on the customer's phone.

        Args:
            creds: Decrypted till credentials.
            phone_number: Customer phone in E.164 without '+' (e.g. 254712345678).
            amount: Amount in KES (no decimals for M-Pesa — will be rounded).
            account_reference: Reference shown to the customer (max 12 chars).
            transaction_desc: Description shown in push prompt (max 13 chars).
            callback_url: Override default callback URL (useful for testing).

        Returns:
            Daraja response dict containing CheckoutRequestID for correlation.

        Raises:
            DarajaError: On API-level failure.
        """
        timestamp = self._current_timestamp()
        password = self._generate_stk_password(
            creds.shortcode, creds.passkey, timestamp
        )
        cb_url = callback_url or settings.daraja_stk_callback_url
        int_amount = int(amount.to_integral_value())

        payload = {
            "BusinessShortCode": creds.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int_amount,
            "PartyA": phone_number,
            "PartyB": creds.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": cb_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": transaction_desc[:13],
        }

        headers = await self._auth_headers(creds)
        response = await self._client.post(
            f"{self._base_url}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
        )

        data = self._parse_response(response, "stk_push")
        logger.info(
            "daraja.stk_push_initiated",
            shortcode=creds.shortcode,
            phone=self._mask_phone(phone_number),
            amount=int_amount,
            checkout_id=data.get("CheckoutRequestID"),
        )
        return data

    async def query_stk_push_status(
        self,
        creds: DarajaTillCredentials,
        checkout_request_id: str,
    ) -> dict[str, Any]:
        """
        Query the status of a previously initiated STK Push.
        Use when callback hasn't arrived within expected window.
        """
        timestamp = self._current_timestamp()
        password = self._generate_stk_password(
            creds.shortcode, creds.passkey, timestamp
        )

        payload = {
            "BusinessShortCode": creds.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        headers = await self._auth_headers(creds)
        response = await self._client.post(
            f"{self._base_url}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers=headers,
        )

        data = self._parse_response(response, "stk_query")
        logger.info(
            "daraja.stk_query",
            checkout_id=checkout_request_id,
            result_code=data.get("ResultCode"),
        )
        return data

    # ── B2C (Business to Customer Disbursement) ───────────────

    async def initiate_b2c(
        self,
        creds: DarajaTillCredentials,
        initiator_name: str,
        security_credential: str,
        phone_number: str,
        amount: Decimal,
        command_id: str,
        remarks: str,
        occasion: str = "",
    ) -> dict[str, Any]:
        """
        Disburse funds from business shortcode to a customer phone.
        Used for Smart Float auto-transfers.

        command_id options:
            - 'SalaryPayment'
            - 'BusinessPayment'  ← use for general transfers
            - 'PromotionPayment'
        """
        int_amount = int(amount.to_integral_value())

        payload = {
            "InitiatorName": initiator_name,
            "SecurityCredential": security_credential,
            "CommandID": command_id,
            "Amount": int_amount,
            "PartyA": creds.shortcode,
            "PartyB": phone_number,
            "Remarks": remarks[:100],
            "QueueTimeOutURL": f"{settings.daraja_callback_base_url}/api/v1/daraja/b2c-timeout",
            "ResultURL": settings.daraja_b2c_result_url,
            "Occasion": occasion[:100],
        }

        headers = await self._auth_headers(creds)
        response = await self._client.post(
            f"{self._base_url}/mpesa/b2c/v3/paymentrequest",
            json=payload,
            headers=headers,
        )

        data = self._parse_response(response, "b2c")
        logger.info(
            "daraja.b2c_initiated",
            shortcode=creds.shortcode,
            phone=self._mask_phone(phone_number),
            amount=int_amount,
            conversation_id=data.get("ConversationID"),
        )
        return data

    # ── C2B URL Registration ──────────────────────────────────

    async def register_c2b_urls(
        self,
        creds: DarajaTillCredentials,
        response_type: str = "Completed",
    ) -> dict[str, Any]:
        """
        Register C2B callback URLs with Safaricom.
        Must be called once when a new till is added (or URLs change).

        response_type: 'Completed' or 'Cancelled'
        """
        payload = {
            "ShortCode": creds.shortcode,
            "ResponseType": response_type,
            "ConfirmationURL": settings.daraja_c2b_confirmation_url,
            "ValidationURL": f"{settings.daraja_callback_base_url}/api/v1/daraja/c2b-validation",
        }

        headers = await self._auth_headers(creds)
        response = await self._client.post(
            f"{self._base_url}/mpesa/c2b/v2/registerurl",
            json=payload,
            headers=headers,
        )

        data = self._parse_response(response, "c2b_register")
        logger.info("daraja.c2b_urls_registered", shortcode=creds.shortcode)
        return data

    # ── Account Balance ───────────────────────────────────────

    async def query_account_balance(
        self,
        creds: DarajaTillCredentials,
        initiator_name: str,
        security_credential: str,
        identifier_type: str = "4",
        remarks: str = "Balance query",
    ) -> dict[str, Any]:
        """
        Query account balance for a shortcode.
        Response arrives via callback — this initiates the query.

        identifier_type:
            '1' = MSISDN, '2' = Till Number, '4' = Shortcode (Paybill)
        """
        payload = {
            "Initiator": initiator_name,
            "SecurityCredential": security_credential,
            "CommandID": "AccountBalance",
            "PartyA": creds.shortcode,
            "IdentifierType": identifier_type,
            "Remarks": remarks,
            "QueueTimeOutURL": f"{settings.daraja_callback_base_url}/api/v1/daraja/balance-timeout",
            "ResultURL": f"{settings.daraja_callback_base_url}/api/v1/daraja/balance-result",
        }

        headers = await self._auth_headers(creds)
        response = await self._client.post(
            f"{self._base_url}/mpesa/accountbalance/v1/query",
            json=payload,
            headers=headers,
        )

        data = self._parse_response(response, "balance_query")
        logger.info(
            "daraja.balance_query_initiated",
            shortcode=creds.shortcode,
            conversation_id=data.get("ConversationID"),
        )
        return data

    # ── Transaction Status ────────────────────────────────────

    async def query_transaction_status(
        self,
        creds: DarajaTillCredentials,
        initiator_name: str,
        security_credential: str,
        transaction_id: str,
        identifier_type: str = "4",
        remarks: str = "Status check",
        occasion: str = "",
    ) -> dict[str, Any]:
        """
        Query the status of a specific transaction by M-Pesa transaction ID.
        Useful for reconciliation when callbacks are delayed or missed.
        """
        payload = {
            "Initiator": initiator_name,
            "SecurityCredential": security_credential,
            "CommandID": "TransactionStatusQuery",
            "TransactionID": transaction_id,
            "PartyA": creds.shortcode,
            "IdentifierType": identifier_type,
            "ResultURL": f"{settings.daraja_callback_base_url}/api/v1/daraja/transaction-status-result",
            "QueueTimeOutURL": f"{settings.daraja_callback_base_url}/api/v1/daraja/transaction-status-timeout",
            "Remarks": remarks,
            "Occasion": occasion,
        }

        headers = await self._auth_headers(creds)
        response = await self._client.post(
            f"{self._base_url}/mpesa/transactionstatus/v1/query",
            json=payload,
            headers=headers,
        )

        data = self._parse_response(response, "transaction_status")
        logger.info(
            "daraja.transaction_status_queried",
            transaction_id=transaction_id,
            shortcode=creds.shortcode,
        )
        return data

    # ── Response parsing ─────────────────────────────────────

    def _parse_response(self, response: httpx.Response, operation: str) -> dict[str, Any]:
        """
        Unified Daraja response parser.
        Raises DarajaError on HTTP errors or Daraja-level failures.
        """
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "daraja.http_error",
                operation=operation,
                status_code=response.status_code,
                body=response.text[:500],
            )
            raise DarajaError(
                f"Daraja HTTP {response.status_code} on {operation}",
                raw={"status_code": response.status_code, "body": response.text},
            ) from exc

        try:
            data: dict = response.json()
        except Exception as exc:
            raise DarajaError(
                f"Daraja returned non-JSON on {operation}",
                raw={"body": response.text},
            ) from exc

        # Check application-level error codes
        result_code = str(data.get("ResultCode", data.get("errorCode", "")))
        if result_code and result_code not in (DARAJA_SUCCESS_CODE, ""):
            error_msg = data.get("ResultDesc", data.get("errorMessage", "Unknown Daraja error"))
            logger.warning(
                "daraja.api_error",
                operation=operation,
                result_code=result_code,
                message=error_msg,
            )
            raise DarajaError(error_msg, result_code=result_code, raw=data)

        return data

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _mask_phone(phone: str) -> str:
        """Mask phone for safe logging: 254712345678 → 2547****5678"""
        if len(phone) >= 8:
            return f"{phone[:4]}****{phone[-4:]}"
        return "****"

    @staticmethod
    def parse_balance_result(result_parameters: list[dict]) -> dict[str, Decimal]:
        """
        Parse the AccountBalance callback ResultParameters into a clean dict.

        Daraja returns balance as:
        "Working Account|KES|12345.00|12345.00|0.00|0.00"

        Returns: {"Working Account": Decimal("12345.00"), ...}
        """
        balances: dict[str, Decimal] = {}
        for param in result_parameters:
            if param.get("Key") == "AccountBalance":
                raw_value: str = param.get("Value", "")
                for segment in raw_value.split("&"):
                    parts = segment.split("|")
                    if len(parts) >= 3:
                        account_name = parts[0].strip()
                        try:
                            available_balance = Decimal(parts[2].strip())
                            balances[account_name] = available_balance
                        except Exception:
                            logger.warning(
                                "daraja.balance_parse_error",
                                segment=segment,
                            )
        return balances

    @staticmethod
    def normalize_phone(raw_phone: str) -> str:
        """
        Normalize a Kenyan phone number to E.164 without '+'.
        Accepts: 0712345678, +254712345678, 254712345678
        Returns: 254712345678
        Raises: ValueError on unrecognized format.
        """
        phone = raw_phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("+254"):
            return phone[1:]
        if phone.startswith("254") and len(phone) == 12:
            return phone
        if phone.startswith("0") and len(phone) == 10:
            return f"254{phone[1:]}"
        raise ValueError(f"Unrecognized Kenyan phone format: {raw_phone}")


# ── Singleton accessor (used as FastAPI dependency) ───────────

_daraja_service: DarajaService | None = None


def get_daraja_service() -> DarajaService:
    global _daraja_service
    if _daraja_service is None:
        _daraja_service = DarajaService()
    return _daraja_service