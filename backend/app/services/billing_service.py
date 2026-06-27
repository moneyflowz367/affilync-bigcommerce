"""
BigCommerce Billing Service
Handles subscription billing for the BigCommerce integration.

Supports:
- 4 plans: Free ($0), Starter ($29/mo), Pro ($99/mo), Enterprise ($299/mo)
- Subscription CRUD: create, get, upgrade, downgrade, cancel
- Grace period handling for downgrades
- Usage tracking against plan limits
- Feature gate checks per plan tier

Ported verbatim from the TikTok Shop integration's billing service so both
e-commerce integrations share an identical plan ladder and mechanism. Billing
is managed directly via the Affilync platform's own subscription database
(BigCommerce, like TikTok, has no native app-billing API).

Note: BigCommerce has products + conversions but no "creators" concept. The
max_creators limit is retained in the plan ladder for parity with TikTok, but
creator usage is always 0 and is omitted from the usage endpoint. Conversions
are forwarded to the Affilync API rather than stored locally, so conversion
usage is read from the subscription's own counter.
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from app.models import BigCommerceProduct, BigCommerceStore
from app.models.subscription import BigCommerceSubscription
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Grace period duration in days when a subscription lapses
GRACE_PERIOD_DAYS = 3


class BillingPlan(str, Enum):
    """Available subscription plans"""

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PlanDetails(BaseModel):
    """Plan configuration"""

    name: str
    price: Decimal
    trial_days: int
    features: list[str]
    max_products: int  # Max products synced to marketplace
    max_creators: int  # Max affiliate creators (parity with TikTok; unused on BC)
    conversion_limit: int  # Monthly conversion limit (-1 = unlimited)
    analytics_depth_days: int  # How far back analytics go
    export_enabled: bool  # CSV/PDF export
    api_access: bool  # API access for custom integrations
    priority_support: bool


# Plan configurations — identical ladder to the TikTok integration
PLANS = {
    BillingPlan.FREE: PlanDetails(
        name="Free",
        price=Decimal("0"),
        trial_days=0,
        features=[
            "Up to 50 products",
            "5 creators",
            "100 conversions/month",
            "7-day analytics",
            "Basic reporting",
        ],
        max_products=50,
        max_creators=5,
        conversion_limit=100,
        analytics_depth_days=7,
        export_enabled=False,
        api_access=False,
        priority_support=False,
    ),
    BillingPlan.STARTER: PlanDetails(
        name="Starter",
        price=Decimal("29"),
        trial_days=7,
        features=[
            "Up to 500 products",
            "25 creators",
            "1,000 conversions/month",
            "30-day analytics",
            "CSV export",
            "Email support",
        ],
        max_products=500,
        max_creators=25,
        conversion_limit=1000,
        analytics_depth_days=30,
        export_enabled=True,
        api_access=False,
        priority_support=False,
    ),
    BillingPlan.PRO: PlanDetails(
        name="Pro",
        price=Decimal("99"),
        trial_days=7,
        features=[
            "Up to 5,000 products",
            "100 creators",
            "10,000 conversions/month",
            "90-day analytics",
            "CSV + PDF export",
            "API access",
            "Priority support",
        ],
        max_products=5000,
        max_creators=100,
        conversion_limit=10000,
        analytics_depth_days=90,
        export_enabled=True,
        api_access=True,
        priority_support=True,
    ),
    BillingPlan.ENTERPRISE: PlanDetails(
        name="Enterprise",
        price=Decimal("299"),
        trial_days=14,
        features=[
            "Unlimited products",
            "Unlimited creators",
            "Unlimited conversions",
            "365-day analytics",
            "Full export suite",
            "API access",
            "Dedicated account manager",
            "Custom integrations",
            "SLA guarantee",
        ],
        max_products=-1,  # Unlimited
        max_creators=-1,  # Unlimited
        conversion_limit=-1,  # Unlimited
        analytics_depth_days=365,
        export_enabled=True,
        api_access=True,
        priority_support=True,
    ),
}

# Ordered plan tiers for upgrade/downgrade detection
PLAN_ORDER = [BillingPlan.FREE, BillingPlan.STARTER, BillingPlan.PRO, BillingPlan.ENTERPRISE]


class BillingError(Exception):
    """Exception raised for billing errors"""

    pass


class BillingService:
    """
    Service for managing BigCommerce billing subscriptions.

    Uses a local subscription table (not a native app billing API) because
    BigCommerce does not provide an app billing mechanism like Shopify.
    Subscriptions are managed through the Affilync platform.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_current_plan(self, store_id: UUID) -> tuple[BillingPlan, Optional[dict]]:
        """
        Get the current subscription plan for a store.

        Returns:
            Tuple of (plan, subscription_dict)
        """
        result = await self.db.execute(
            select(BigCommerceSubscription).where(BigCommerceSubscription.store_id == store_id)
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return BillingPlan.FREE, None

        # Check for grace period expiry
        if subscription.status == "grace_period" and subscription.grace_period_ends:
            if subscription.grace_period_ends < datetime.now(timezone.utc):
                logger.info("Grace period expired for store %s, downgrading to free", store_id)
                subscription.previous_plan = subscription.plan
                subscription.plan = BillingPlan.FREE.value
                subscription.status = "active"
                subscription.downgrade_reason = "grace_period_expired"
                subscription.grace_period_ends = None
                subscription.price_cents = 0
                subscription.updated_at = datetime.now(timezone.utc)
                await self.db.commit()
                return BillingPlan.FREE, subscription.to_dict()

        try:
            plan = BillingPlan(subscription.plan)
        except ValueError:
            plan = BillingPlan.FREE

        return plan, subscription.to_dict()

    async def create_subscription(
        self,
        store_id: UUID,
        plan: BillingPlan,
    ) -> dict:
        """
        Create or update a subscription for a store.

        Handles upgrades (immediate) and downgrades (grace period at period end).

        Args:
            store_id: The store UUID
            plan: The target plan

        Returns:
            dict with subscription details
        """
        # Validate store exists
        store_result = await self.db.execute(
            select(BigCommerceStore).where(BigCommerceStore.id == store_id)
        )
        store = store_result.scalar_one_or_none()
        if not store:
            raise BillingError("Store not found")

        # Get or create subscription
        result = await self.db.execute(
            select(BigCommerceSubscription).where(BigCommerceSubscription.store_id == store_id)
        )
        subscription = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        plan_details = PLANS[plan]

        if subscription:
            current_plan = BillingPlan(subscription.plan)

            if current_plan == plan:
                return {
                    "status": "no_change",
                    "message": f"Already on {plan.value} plan",
                    "plan": plan.value,
                }

            is_upgrade = self._is_upgrade(current_plan, plan)

            if is_upgrade:
                # Immediate upgrade
                subscription.previous_plan = subscription.plan
                subscription.plan = plan.value
                subscription.status = "active"
                subscription.price_cents = int(plan_details.price * 100)
                subscription.current_period_start = now
                subscription.current_period_end = now + timedelta(days=30)
                subscription.grace_period_ends = None
                subscription.downgrade_reason = None
                subscription.updated_at = now

                # Reset usage on upgrade
                subscription.conversions_used = 0

                await self.db.commit()
                await self.db.refresh(subscription)

                logger.info(
                    "Store %s upgraded from %s to %s", store_id, current_plan.value, plan.value
                )

                return {
                    "status": "upgraded",
                    "plan": plan.value,
                    "previous_plan": current_plan.value,
                    "subscription": subscription.to_dict(),
                }

            else:
                # Downgrade: takes effect at end of current period
                subscription.previous_plan = subscription.plan
                subscription.plan = plan.value
                subscription.price_cents = int(plan_details.price * 100)
                subscription.downgrade_reason = "user_downgrade"
                subscription.updated_at = now

                # If there's a current period, the downgrade is scheduled
                if subscription.current_period_end and subscription.current_period_end > now:
                    subscription.status = "active"  # Stay active until period end
                    effective_date = subscription.current_period_end.isoformat()
                else:
                    subscription.status = "active"
                    subscription.current_period_start = now
                    subscription.current_period_end = now + timedelta(days=30)
                    effective_date = now.isoformat()

                await self.db.commit()
                await self.db.refresh(subscription)

                logger.info(
                    "Store %s downgraded from %s to %s (effective: %s)",
                    store_id,
                    current_plan.value,
                    plan.value,
                    effective_date,
                )

                return {
                    "status": "downgraded",
                    "plan": plan.value,
                    "previous_plan": current_plan.value,
                    "effective_date": effective_date,
                    "subscription": subscription.to_dict(),
                }

        else:
            # New subscription
            trial_days = plan_details.trial_days
            trial_ends_at = None
            if trial_days > 0 and plan != BillingPlan.FREE:
                trial_ends_at = now + timedelta(days=trial_days)

            subscription = BigCommerceSubscription(
                store_id=store_id,
                plan=plan.value,
                status="active",
                price_cents=int(plan_details.price * 100),
                currency="USD",
                trial_days=trial_days,
                trial_ends_at=trial_ends_at,
                current_period_start=now,
                current_period_end=now + timedelta(days=30),
                created_at=now,
                updated_at=now,
            )

            self.db.add(subscription)
            await self.db.commit()
            await self.db.refresh(subscription)

            logger.info("Store %s subscribed to %s plan", store_id, plan.value)

            return {
                "status": "subscribed",
                "plan": plan.value,
                "trial_days": trial_days,
                "subscription": subscription.to_dict(),
            }

    async def cancel_subscription(self, store_id: UUID) -> dict:
        """
        Cancel the current subscription.

        Downgrades to the free plan. If within a billing period, access
        continues until the period ends.

        Args:
            store_id: The store UUID

        Returns:
            dict with cancellation details
        """
        result = await self.db.execute(
            select(BigCommerceSubscription).where(BigCommerceSubscription.store_id == store_id)
        )
        subscription = result.scalar_one_or_none()

        if not subscription or subscription.plan == BillingPlan.FREE.value:
            return {"status": "no_subscription", "message": "No active paid subscription"}

        now = datetime.now(timezone.utc)
        previous_plan = subscription.plan

        # Determine when access ends
        access_until = None
        if subscription.current_period_end and subscription.current_period_end > now:
            access_until = subscription.current_period_end.isoformat()

        subscription.previous_plan = previous_plan
        subscription.plan = BillingPlan.FREE.value
        subscription.status = "cancelled"
        subscription.price_cents = 0
        subscription.cancelled_at = now
        subscription.downgrade_reason = "user_cancelled"
        subscription.updated_at = now

        await self.db.commit()

        logger.info("Store %s cancelled subscription (was: %s)", store_id, previous_plan)

        return {
            "status": "cancelled",
            "previous_plan": previous_plan,
            "access_until": access_until,
        }

    async def get_usage(self, store_id: UUID) -> dict:
        """
        Get current usage statistics against plan limits.

        BigCommerce tracks products locally but forwards conversions to the
        Affilync API (no local conversions table) and has no "creators"
        concept. Conversion usage is therefore read from the subscription's
        own counter, and creators are omitted from the response.

        Args:
            store_id: The store UUID

        Returns:
            dict with usage stats
        """
        plan, sub_dict = await self.get_current_plan(store_id)
        plan_details = PLANS[plan]

        # Get actual product count (visible/synced products for this store)
        product_count_result = await self.db.execute(
            select(func.count(BigCommerceProduct.id)).where(
                BigCommerceProduct.store_id == store_id,
                BigCommerceProduct.is_visible.is_(True),
            )
        )
        products_used = product_count_result.scalar_one() or 0

        # Conversions are tracked via the Affilync API, not stored locally;
        # use the subscription's running counter as the local source of truth.
        conversions_used = (sub_dict or {}).get("conversions_used", 0) or 0

        # Calculate remaining quotas
        def _remaining(used: int, limit: int) -> int:
            if limit == -1:
                return -1  # Unlimited
            return max(0, limit - used)

        def _percentage(used: int, limit: int) -> int:
            if limit <= 0:
                return 0
            return min(100, int((used / limit) * 100))

        return {
            "plan": plan.value,
            "usage": {
                "products": {
                    "used": products_used,
                    "limit": plan_details.max_products,
                    "remaining": _remaining(products_used, plan_details.max_products),
                    "percentage": _percentage(products_used, plan_details.max_products),
                },
                "conversions": {
                    "used": conversions_used,
                    "limit": plan_details.conversion_limit,
                    "remaining": _remaining(conversions_used, plan_details.conversion_limit),
                    "percentage": _percentage(conversions_used, plan_details.conversion_limit),
                },
            },
            "features": {
                "analytics_depth_days": plan_details.analytics_depth_days,
                "export_enabled": plan_details.export_enabled,
                "api_access": plan_details.api_access,
                "priority_support": plan_details.priority_support,
            },
            "period": "current_month",
        }

    async def check_feature_access(self, store_id: UUID, feature: str) -> bool:
        """
        Check if a store has access to a specific feature based on plan.

        Args:
            store_id: The store UUID
            feature: Feature name to check

        Returns:
            True if feature is available
        """
        plan, sub_dict = await self.get_current_plan(store_id)

        # Allow access during grace period
        if sub_dict and sub_dict.get("status") == "grace_period":
            grace_ends = sub_dict.get("grace_period_ends")
            if grace_ends:
                try:
                    grace_dt = datetime.fromisoformat(grace_ends)
                    if grace_dt >= datetime.now(timezone.utc):
                        prev_plan = BillingPlan(sub_dict.get("previous_plan", "free"))
                        return feature in PLANS[prev_plan].features
                except (ValueError, KeyError):
                    pass

        plan_details = PLANS[plan]
        return feature in plan_details.features

    async def check_limit(
        self, store_id: UUID, resource: str, current_count: int
    ) -> tuple[bool, int]:
        """
        Check if a store is within a resource limit.

        Args:
            store_id: The store UUID
            resource: "products", "creators", or "conversions"
            current_count: Current usage count

        Returns:
            Tuple of (within_limit, remaining)
        """
        plan, _ = await self.get_current_plan(store_id)
        plan_details = PLANS[plan]

        limit_map = {
            "products": plan_details.max_products,
            "creators": plan_details.max_creators,
            "conversions": plan_details.conversion_limit,
        }

        limit = limit_map.get(resource, 0)

        if limit == -1:
            return True, -1  # Unlimited

        remaining = limit - current_count
        return remaining > 0, max(0, remaining)

    def _is_upgrade(self, current: BillingPlan, target: BillingPlan) -> bool:
        """Check if changing from current to target is an upgrade."""
        try:
            return PLAN_ORDER.index(target) > PLAN_ORDER.index(current)
        except ValueError:
            return False
