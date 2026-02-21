"""Autumn billing integration.

Autumn (https://useautumn.com) manages feature access, usage limits, and billing.
This module wraps the Autumn REST API so the rest of Foundry can call
``check()``, ``track()``, and ``checkout()`` without knowing HTTP details.

Configuration:
    AUTUMN_SECRET_KEY  – Your Autumn secret key (``am_sk_...``).
                         When absent every call is a no-op that returns "allowed".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from src.infra.logging import get_logger

logger = get_logger("autumn")

AUTUMN_BASE_URL = "https://api.useautumn.com/v1"

# Feature IDs (must match what was created in Autumn dashboard)
FEATURE_BUILDS = "builds"
FEATURE_INVOCATIONS = "invocations"
FEATURE_SEARCHES = "searches"

# Map internal event types to Autumn feature IDs
EVENT_TO_FEATURE: Dict[str, str] = {
    "tool_build": FEATURE_BUILDS,
    "tool_invoke": FEATURE_INVOCATIONS,
    "search": FEATURE_SEARCHES,
}


# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    """Result of an Autumn ``/check`` call."""

    allowed: bool
    code: str = "ok"
    balance: Optional[int] = None
    usage: Optional[int] = None
    included_usage: Optional[int] = None
    unlimited: bool = False
    error: Optional[str] = None


@dataclass
class TrackResult:
    """Result of an Autumn ``/track`` call."""

    success: bool
    customer_id: Optional[str] = None
    feature_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CheckoutResult:
    """Result of an Autumn ``/checkout`` call."""

    checkout_url: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class AutumnClient:
    """Thin async wrapper around the Autumn REST API."""

    def __init__(self, secret_key: Optional[str] = None):
        self._secret_key = secret_key or os.environ.get("AUTUMN_SECRET_KEY", "")
        self._enabled = bool(self._secret_key)
        if self._enabled:
            logger.info("Autumn billing integration enabled")
        else:
            logger.warning("Autumn billing not configured (AUTUMN_SECRET_KEY missing) — all checks will pass")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Check — can the customer use this feature?
    # ------------------------------------------------------------------

    async def check(
        self,
        customer_id: str,
        feature_id: str,
        *,
        required_balance: int = 1,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> CheckResult:
        """Check if *customer_id* has access to *feature_id*.

        If Autumn is not configured every call returns ``allowed=True``.
        Autumn auto-creates unknown customers and assigns the default
        product (Free) on first check.
        """
        if not self._enabled:
            return CheckResult(allowed=True, code="autumn_disabled", unlimited=True)

        body: Dict[str, Any] = {
            "customer_id": customer_id,
            "feature_id": feature_id,
            "required_balance": required_balance,
        }
        if customer_data:
            body["customer_data"] = customer_data

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{AUTUMN_BASE_URL}/check",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

            return CheckResult(
                allowed=data.get("allowed", False),
                code=data.get("code", ""),
                balance=data.get("balance"),
                usage=data.get("usage"),
                included_usage=data.get("included_usage"),
                unlimited=data.get("unlimited", False),
            )

        except httpx.HTTPStatusError as e:
            body_text = e.response.text
            logger.error(f"Autumn check failed ({e.response.status_code}): {body_text}")
            # Fail open — don't block the user if Autumn is temporarily down
            return CheckResult(allowed=True, code="autumn_error", error=body_text)

        except Exception as e:
            logger.error(f"Autumn check error: {e}")
            return CheckResult(allowed=True, code="autumn_error", error=str(e))

    # ------------------------------------------------------------------
    # Track — record a usage event
    # ------------------------------------------------------------------

    async def track(
        self,
        customer_id: str,
        feature_id: str,
        *,
        value: int = 1,
        properties: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> TrackResult:
        """Record a usage event for *customer_id* / *feature_id*.

        Fire-and-forget friendly — failures are logged but never raised.
        """
        if not self._enabled:
            return TrackResult(success=True, customer_id=customer_id, feature_id=feature_id)

        body: Dict[str, Any] = {
            "customer_id": customer_id,
            "feature_id": feature_id,
            "value": value,
        }
        if properties:
            body["properties"] = properties
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
        if customer_data:
            body["customer_data"] = customer_data

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{AUTUMN_BASE_URL}/track",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

            return TrackResult(
                success=True,
                customer_id=data.get("customer_id", customer_id),
                feature_id=data.get("feature_id", feature_id),
            )

        except Exception as e:
            logger.error(f"Autumn track error for {customer_id}/{feature_id}: {e}")
            return TrackResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Checkout — generate a Stripe checkout URL for plan upgrade
    # ------------------------------------------------------------------

    async def checkout(
        self,
        customer_id: str,
        product_id: str,
        *,
        success_url: str = "https://foundry.ai/dashboard?upgraded=1",
        cancel_url: str = "https://foundry.ai/pricing",
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> CheckoutResult:
        """Create a Stripe checkout session via Autumn.

        Returns a ``checkout_url`` the frontend can redirect to.
        """
        if not self._enabled:
            return CheckoutResult(error="Autumn billing not configured")

        body: Dict[str, Any] = {
            "customer_id": customer_id,
            "product_id": product_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if customer_data:
            body["customer_data"] = customer_data

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{AUTUMN_BASE_URL}/checkout",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

            return CheckoutResult(checkout_url=data.get("checkout_url") or data.get("url"))

        except httpx.HTTPStatusError as e:
            body_text = e.response.text
            logger.error(f"Autumn checkout failed ({e.response.status_code}): {body_text}")
            return CheckoutResult(error=body_text)

        except Exception as e:
            logger.error(f"Autumn checkout error: {e}")
            return CheckoutResult(error=str(e))

    # ------------------------------------------------------------------
    # Customer — create customer (called on org registration)
    # ------------------------------------------------------------------

    async def create_customer(
        self,
        customer_id: str,
        *,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Explicitly create a customer in Autumn.

        Autumn auto-creates on ``/check``, but explicit creation lets us
        pass name/email upfront.  Idempotent — re-creating returns the
        existing customer.
        """
        if not self._enabled:
            return {"customer_id": customer_id, "status": "autumn_disabled"}

        body: Dict[str, Any] = {"id": customer_id}
        if name:
            body["name"] = name
        if email:
            body["email"] = email

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{AUTUMN_BASE_URL}/customers",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            logger.error(f"Autumn create_customer error: {e}")
            return {"customer_id": customer_id, "error": str(e)}

    # ------------------------------------------------------------------
    # Attach — attach a product to a customer (free plan on signup)
    # ------------------------------------------------------------------

    async def attach(
        self,
        customer_id: str,
        product_id: str,
        *,
        customer_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Attach a product to a customer.

        Used during registration to attach the Free plan automatically.
        """
        if not self._enabled:
            return {"customer_id": customer_id, "status": "autumn_disabled"}

        body: Dict[str, Any] = {
            "customer_id": customer_id,
            "product_id": product_id,
        }
        if customer_data:
            body["customer_data"] = customer_data

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{AUTUMN_BASE_URL}/attach",
                    headers=self._headers(),
                    json=body,
                )
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            logger.error(f"Autumn attach error: {e}")
            return {"customer_id": customer_id, "error": str(e)}

    # ------------------------------------------------------------------
    # Get customer
    # ------------------------------------------------------------------

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """Fetch customer details from Autumn."""
        if not self._enabled:
            return {"id": customer_id, "status": "autumn_disabled"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{AUTUMN_BASE_URL}/customers/{customer_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            logger.error(f"Autumn get_customer error: {e}")
            return {"id": customer_id, "error": str(e)}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_autumn_instance: Optional[AutumnClient] = None


def get_autumn() -> AutumnClient:
    """Get the global Autumn client (lazy singleton)."""
    global _autumn_instance
    if _autumn_instance is None:
        _autumn_instance = AutumnClient()
    return _autumn_instance
