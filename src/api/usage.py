"""Usage tracking and billing endpoints.

Provides usage stats and billing information for organizations.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import AuthContext, require_auth
from src.infra.database import get_db
from src.infra.logging import get_logger

logger = get_logger("api.usage")

usage_router = APIRouter(prefix="/v1/usage", tags=["Usage & Billing"])


class UsageStats(BaseModel):
    builds: int = 0
    invocations: int = 0
    searches: int = 0
    builds_limit: int = 100
    invocations_limit: int = 1000
    searches_limit: int = 500
    plan: str = "free"


class UsageEvent(BaseModel):
    event_type: str
    tool_id: Optional[str]
    execution_time_ms: int
    tokens_used: int
    created_at: str


class DetailedUsage(BaseModel):
    stats: UsageStats
    recent_events: List[UsageEvent]
    estimated_cost_usd: float = 0.0


class PlanInfo(BaseModel):
    id: str
    name: str
    price_monthly_usd: float
    monthly_builds: int
    monthly_invocations: int
    monthly_searches: int
    features: Dict


class PlansResponse(BaseModel):
    plans: List[PlanInfo]
    current_plan: str


@usage_router.get("/current", response_model=UsageStats)
async def get_current_usage(
    auth: AuthContext = Depends(require_auth),
):
    """Get current month usage for the authenticated organization."""
    db = get_db()
    
    if not db.is_configured:
        return UsageStats(
            plan=auth.plan,
            builds_limit=auth.monthly_build_limit,
            invocations_limit=auth.monthly_invoke_limit,
            searches_limit=auth.monthly_search_limit,
        )
    
    result = await db.execute_one(
        "SELECT * FROM get_current_usage($1)",
        [auth.org_id],
    )
    
    return UsageStats(
        builds=result.get("builds", 0) if result else 0,
        invocations=result.get("invocations", 0) if result else 0,
        searches=result.get("searches", 0) if result else 0,
        builds_limit=auth.monthly_build_limit,
        invocations_limit=auth.monthly_invoke_limit,
        searches_limit=auth.monthly_search_limit,
        plan=auth.plan,
    )


@usage_router.get("/detailed", response_model=DetailedUsage)
async def get_detailed_usage(
    auth: AuthContext = Depends(require_auth),
):
    """Get detailed usage stats and recent events."""
    db = get_db()
    
    if not db.is_configured:
        return DetailedUsage(
            stats=UsageStats(
                plan=auth.plan,
                builds_limit=auth.monthly_build_limit,
                invocations_limit=auth.monthly_invoke_limit,
                searches_limit=auth.monthly_search_limit,
            ),
            recent_events=[],
        )
    
    # Get stats
    stats_result = await db.execute_one(
        "SELECT * FROM get_current_usage($1)",
        [auth.org_id],
    )
    
    # Get recent events
    events = await db.execute(
        """
        SELECT event_type, tool_id, execution_time_ms, tokens_used, 
               created_at::text
        FROM usage_events
        WHERE org_id = $1
        ORDER BY created_at DESC
        LIMIT 50
        """,
        [auth.org_id],
    )
    
    # Get estimated cost
    cost_result = await db.execute_one(
        """
        SELECT COALESCE(SUM(estimated_cost_usd), 0) as total_cost
        FROM usage_events
        WHERE org_id = $1
        AND created_at >= date_trunc('month', NOW())
        """,
        [auth.org_id],
    )
    
    return DetailedUsage(
        stats=UsageStats(
            builds=stats_result.get("builds", 0) if stats_result else 0,
            invocations=stats_result.get("invocations", 0) if stats_result else 0,
            searches=stats_result.get("searches", 0) if stats_result else 0,
            builds_limit=auth.monthly_build_limit,
            invocations_limit=auth.monthly_invoke_limit,
            searches_limit=auth.monthly_search_limit,
            plan=auth.plan,
        ),
        recent_events=[
            UsageEvent(
                event_type=e["event_type"],
                tool_id=e.get("tool_id"),
                execution_time_ms=e.get("execution_time_ms", 0),
                tokens_used=e.get("tokens_used", 0),
                created_at=e["created_at"],
            )
            for e in events
        ],
        estimated_cost_usd=float(cost_result.get("total_cost", 0)) if cost_result else 0,
    )


@usage_router.get("/plans", response_model=PlansResponse)
async def get_plans(
    auth: AuthContext = Depends(require_auth),
):
    """Get available billing plans."""
    db = get_db()
    
    if not db.is_configured:
        return PlansResponse(
            plans=[
                PlanInfo(
                    id="free", name="Free", price_monthly_usd=0,
                    monthly_builds=100, monthly_invocations=1000, monthly_searches=500,
                    features={"polymarket": True, "exa_search": False},
                ),
                PlanInfo(
                    id="pro", name="Pro", price_monthly_usd=49,
                    monthly_builds=1000, monthly_invocations=25000, monthly_searches=5000,
                    features={"polymarket": True, "exa_search": True, "priority_builds": True},
                ),
                PlanInfo(
                    id="scale", name="Scale", price_monthly_usd=199,
                    monthly_builds=10000, monthly_invocations=250000, monthly_searches=50000,
                    features={"polymarket": True, "exa_search": True, "priority_builds": True, "sla": True},
                ),
            ],
            current_plan=auth.plan,
        )
    
    rows = await db.execute(
        """
        SELECT id, name, price_monthly_usd, monthly_builds, 
               monthly_invocations, monthly_searches, features
        FROM billing_plans
        WHERE is_active = TRUE
        ORDER BY price_monthly_usd
        """,
    )
    
    return PlansResponse(
        plans=[
            PlanInfo(
                id=row["id"],
                name=row["name"],
                price_monthly_usd=float(row["price_monthly_usd"]),
                monthly_builds=row["monthly_builds"],
                monthly_invocations=row["monthly_invocations"],
                monthly_searches=row["monthly_searches"],
                features=row.get("features", {}),
            )
            for row in rows
        ],
        current_plan=auth.plan,
    )
