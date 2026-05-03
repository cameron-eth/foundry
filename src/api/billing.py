"""Billing endpoints — checkout, plan management, and usage summaries via Autumn.

All endpoints require authentication (valid API key).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.api.auth import AuthContext, require_auth
from src.infra.autumn import get_autumn
from src.infra.logging import get_logger

logger = get_logger("api.billing")

billing_router = APIRouter(prefix="/v1/billing", tags=["Billing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    """Request a Stripe checkout URL for a plan upgrade."""
    product_id: str = Field(description="Product to subscribe to: free, pro, pro_annual, scale, scale_annual")
    success_url: Optional[str] = Field(
        default=None,
        description="URL to redirect to after successful payment",
    )
    cancel_url: Optional[str] = Field(
        default=None,
        description="URL to redirect to if the user cancels checkout",
    )


class CheckoutResponse(BaseModel):
    checkout_url: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


class EntitlementRequest(BaseModel):
    """Check if the org can use a specific feature."""
    feature_id: str = Field(description="Feature to check: builds, invocations, searches")


class EntitlementResponse(BaseModel):
    allowed: bool
    feature_id: str
    balance: Optional[int] = None
    usage: Optional[int] = None
    included_usage: Optional[int] = None
    unlimited: bool = False


class BillingStatusResponse(BaseModel):
    """Current billing status for the org."""
    org_id: str
    autumn_enabled: bool
    features: dict = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@billing_router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    auth: AuthContext = Depends(require_auth),
):
    """Create a Stripe checkout URL for a plan upgrade.
    
    Redirect the user to the returned ``checkout_url`` to complete payment.
    Autumn handles the Stripe integration, webhook processing, and plan activation.
    """
    autumn = get_autumn()

    if not autumn.is_enabled:
        raise HTTPException(
            status_code=503,
            detail="Billing system not configured. Contact support.",
        )

    valid_products = {"paygo", "pro"}
    if request.product_id not in valid_products:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid product_id '{request.product_id}'. Choose from: {', '.join(sorted(valid_products))}",
        )

    success_url = request.success_url or "http://localhost:3000/dashboard?upgraded=1"
    cancel_url = request.cancel_url or "http://localhost:3000/pricing"

    result = await autumn.checkout(
        customer_id=auth.org_id,
        product_id=request.product_id,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    if result.error:
        logger.error(f"Checkout failed for org {auth.org_id}: {result.error}")
        return CheckoutResponse(
            message="Checkout creation failed",
            error=result.error,
        )

    logger.info(f"Checkout created for org {auth.org_id} -> {request.product_id}")
    return CheckoutResponse(
        checkout_url=result.checkout_url,
        message="Redirect user to checkout_url to complete payment",
    )


@billing_router.post("/check", response_model=EntitlementResponse)
async def check_entitlement(
    request: EntitlementRequest,
    auth: AuthContext = Depends(require_auth),
):
    """Check if the authenticated org can use a specific feature.
    
    Returns current balance, usage, and whether the operation is allowed.
    Useful for frontends to show usage meters and upgrade prompts.
    """
    autumn = get_autumn()

    if not autumn.is_enabled:
        return EntitlementResponse(
            allowed=True,
            feature_id=request.feature_id,
            unlimited=True,
        )

    result = await autumn.check(auth.org_id, request.feature_id)

    return EntitlementResponse(
        allowed=result.allowed,
        feature_id=request.feature_id,
        balance=result.balance,
        usage=result.usage,
        included_usage=result.included_usage,
        unlimited=result.unlimited,
    )


@billing_router.get("/status", response_model=BillingStatusResponse)
async def billing_status(
    auth: AuthContext = Depends(require_auth),
):
    """Get the current billing status for the authenticated org.
    
    Returns feature balances, usage, and limits across all features.
    """
    autumn = get_autumn()

    features = {}

    if autumn.is_enabled:
        for feature_id in ["builds", "invocations", "searches"]:
            result = await autumn.check(auth.org_id, feature_id)
            features[feature_id] = {
                "allowed": result.allowed,
                "balance": result.balance,
                "usage": result.usage,
                "included_usage": result.included_usage,
                "unlimited": result.unlimited,
            }

    return BillingStatusResponse(
        org_id=auth.org_id,
        autumn_enabled=autumn.is_enabled,
        features=features,
    )
