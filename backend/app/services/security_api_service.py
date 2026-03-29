"""
Daraja 3.0 Security API Service — privacy-first identity verification.

As of March 2026, Safaricom hides raw MSISDNs in transaction logs
to prevent social engineering. This service uses the Security API
to verify user identity without ever receiving the raw phone number.

Flows:
  1. Mini App login: Exchange M-Pesa auth_code for a verified identity token.
     The backend never sees the user's full phone — only a masked reference.

  2. Transaction verification: Confirm a payer's identity on high-value
     STK Pushes without exposing their MSISDN in our logs.

  3. Fraud signal check: Query the Security API before processing
     any B2C disbursement above KES 10,000.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

import httpx
import structlog

from app.core.config import get_settings
from app.core.redis_client import get_redis

logger = structlog.get_logger(__name__)
settings = get_settings()

# Daraja 3.0 Security API endpoints (sandbox)
SECURITY_API_BASE = f"{settings.daraja_base_url}/mpesa/security/v1"

# Risk thresholds
HIGH_VALUE_THRESHOLD_KES = Decimal("10000.00")
FRAUD_CHECK_CACHE_TTL = 3600  # 1 hour


class SecurityAPIError(Exception):
    def __init__(self, message: str, result_code: str | None = None):
        super().__init__(message)
        self.result_code = result_code


class SecurityAPIService:
    """
    Daraja 3.0 Security API client.
    Stateless — credentials supplied per call.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0),
            headers={"Content-Type": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── Mini App Identity Resolution ──────────────────────

    async def resolve_miniapp_identity(
        self,
        auth_code: str,
        access_token: str,
    ) -> dict:
        """
        Exchange an M-Pesa Super App auth_code for a verified identity.

        The auth_code is a one-time token issued by the M-Pesa Super App
        when a user opens your Mini App. We exchange it for:
          - masked_phone: "2547****5678" — safe to store and display
          - identity_token: opaque reference for subsequent API calls
          - account_tier: basic | standard | premium

        The raw MSISDN is NEVER returned to us — this is by design.
        Safaricom's 2026 privacy compliance requirement.
        """
        payload = {
            "AuthCode": auth_code,
            "RequestType": "MiniAppIdentity",
        }

        try:
            response = await self._client.post(
                f"{SECURITY_API_BASE}/identity/resolve",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("ResultCode") != "0":
                raise SecurityAPIError(
                    data.get("ResultDesc", "Identity resolution failed"),
                    result_code=data.get("ResultCode"),
                )

            result = {
                "masked_phone": data.get("MaskedMSISDN", ""),
                "identity_token": data.get("IdentityToken", ""),
                "account_tier": data.get("AccountTier", "basic"),
                "is_verified": data.get("KYCStatus") == "VERIFIED",
            }

            logger.info(
                "security_api.identity_resolved",
                masked_phone=result["masked_phone"],
                tier=result["account_tier"],
                verified=result["is_verified"],
            )

            return result

        except httpx.HTTPStatusError as exc:
            logger.error(
                "security_api.identity_http_error",
                status=exc.response.status_code,
            )
            raise SecurityAPIError(
                f"Security API HTTP {exc.response.status_code}"
            ) from exc

    # ── Transaction fraud check ───────────────────────────

    async def check_transaction_risk(
        self,
        identity_token: str,
        amount_kes: Decimal,
        transaction_type: str,
        access_token: str,
    ) -> dict:
        """
        Query the Security API for a risk score before processing
        high-value B2C disbursements.

        Returns:
            risk_level: "low" | "medium" | "high"
            allow_proceed: bool
            reason: str (if blocked)

        Only called for transactions above HIGH_VALUE_THRESHOLD_KES.
        Results cached in Redis for 1 hour per identity_token.
        """
        if amount_kes < HIGH_VALUE_THRESHOLD_KES:
            return {"risk_level": "low", "allow_proceed": True, "reason": ""}

        # Check Redis cache first
        redis = get_redis()
        cache_key = f"fraud:check:{hashlib.sha256(identity_token.encode()).hexdigest()[:16]}"
        cached = await redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        payload = {
            "IdentityToken": identity_token,
            "TransactionAmount": str(amount_kes),
            "TransactionType": transaction_type,
            "RequestType": "FraudCheck",
        }

        try:
            response = await self._client.post(
                f"{SECURITY_API_BASE}/fraud/check",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

            risk_level = data.get("RiskLevel", "medium").lower()
            allow_proceed = risk_level in ("low", "medium")

            result = {
                "risk_level": risk_level,
                "allow_proceed": allow_proceed,
                "reason": data.get("BlockReason", "") if not allow_proceed else "",
            }

            # Cache the result
            import json
            await redis.setex(cache_key, FRAUD_CHECK_CACHE_TTL, json.dumps(result))

            logger.info(
                "security_api.fraud_check",
                risk_level=risk_level,
                amount=str(amount_kes),
                allow=allow_proceed,
            )

            return result

        except (httpx.HTTPStatusError, SecurityAPIError) as exc:
            # Fail open on Security API errors — log and allow
            # Real money should not be blocked by an API timeout
            logger.warning(
                "security_api.fraud_check_failed",
                error=str(exc),
                amount=str(amount_kes),
            )
            return {"risk_level": "unknown", "allow_proceed": True, "reason": ""}

    # ── MSISDN masking (local fallback) ───────────────────

    @staticmethod
    def mask_msisdn(phone: str) -> str:
        """
        Local masking for display purposes.
        Used when Security API is unavailable.
        Never used as a substitute for the Security API token.
        Format: 254712345678 → 2547****5678
        """
        if len(phone) >= 8:
            return f"{phone[:4]}****{phone[-4:]}"
        return "****"

    @staticmethod
    def hash_msisdn_for_storage(phone: str) -> str:
        """
        One-way hash of MSISDN for internal correlation.
        Used in audit logs — the raw number is never stored.
        SHA-256 + salt from SECRET_KEY.
        """
        from app.core.config import get_settings
        salt = get_settings().secret_key[:16]
        return hashlib.sha256(f"{salt}:{phone}".encode()).hexdigest()


# ── Singleton ─────────────────────────────────────────────────

_security_service: SecurityAPIService | None = None


def get_security_service() -> SecurityAPIService:
    global _security_service
    if _security_service is None:
        _security_service = SecurityAPIService()
    return _security_service