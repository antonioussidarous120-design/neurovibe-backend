import logging
import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from core.config import settings
from core.database import get_supabase
from core.auth import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialise Stripe with the secret key at import time.
# If the key is blank (local dev without creds), calls will fail gracefully.
stripe.api_key = settings.STRIPE_SECRET_KEY

# ── Price-ID → plan mapping ───────────────────────────────────────────────────
# Hardcoded to survive env-var load-order edge cases and to be the single
# source of truth for how Stripe price IDs map to internal plan names.
PRICE_TO_PLAN: dict[str, str] = {
    "price_1Tmg8KERoS6Hj19rS6aSASfX": "creator",   # creator monthly
    "price_1Tmg8KERoS6Hj19rZL0zQV3q": "creator",   # creator yearly
    "price_1Tmg99ERoS6Hj19rm98GqRpd": "pro",        # pro monthly
    "price_1Tmg9sERoS6Hj19rd7MyJ4C7": "pro",        # pro yearly
}

SUCCESS_URL = "https://getneruovibe.com/dashboard?upgraded=true"
CANCEL_URL  = "https://getneruovibe.com/pricing"
RETURN_URL  = "https://getneruovibe.com/dashboard"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_stripe_customer(db, user_id: str) -> str:
    """Return existing stripe_customer_id or create a new Stripe customer."""
    res = db.table("user_plans").select("stripe_customer_id").eq("user_id", user_id).single().execute()
    existing = (res.data or {}).get("stripe_customer_id")
    if existing:
        return existing

    # Try to get the user's email from Supabase Auth (service role)
    email = None
    try:
        user_res = db.auth.admin.get_user_by_id(user_id)
        email = user_res.user.email if (user_res and user_res.user) else None
    except Exception:
        pass

    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": user_id},
    )
    # Persist immediately so concurrent requests don't create duplicates
    db.table("user_plans").update({"stripe_customer_id": customer.id}).eq("user_id", user_id).execute()
    logger.info(f"[billing] created Stripe customer={customer.id} user={user_id}")
    return customer.id


def _plan_for_price(price_id: str) -> str | None:
    """Map a Stripe price ID to an internal plan name. Returns None if unknown."""
    return PRICE_TO_PLAN.get(price_id)


# ─── POST /api/billing/checkout ───────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    price_id: str


@router.post("/checkout")
async def create_checkout(request: Request, req: CheckoutRequest):
    """
    Create a Stripe Checkout Session for the given price_id.
    Returns { url } — the frontend should redirect window.location.href to it.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured.")

    if req.price_id not in PRICE_TO_PLAN:
        raise HTTPException(status_code=400, detail=f"Unknown price_id: {req.price_id}")

    user_id = get_user_id(request)
    db = get_supabase()

    try:
        customer_id = _get_or_create_stripe_customer(db, user_id)
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": req.price_id, "quantity": 1}],
            mode="subscription",
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            # Metadata lets the webhook identify the user without a DB lookup
            metadata={"user_id": user_id, "price_id": req.price_id},
            subscription_data={"metadata": {"user_id": user_id, "price_id": req.price_id}},
        )
        logger.info(f"[billing] checkout session created user={user_id} price={req.price_id}")
        return {"url": session.url}
    except stripe.StripeError as e:
        logger.error(f"[billing] checkout error user={user_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


# ─── POST /api/billing/portal ─────────────────────────────────────────────────

@router.post("/portal")
async def create_portal(request: Request):
    """
    Create a Stripe Billing Portal session so the user can manage/cancel their
    subscription. Returns { url } — redirect the browser to it.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Billing not configured.")

    user_id = get_user_id(request)
    db = get_supabase()

    res = db.table("user_plans").select("stripe_customer_id").eq("user_id", user_id).single().execute()
    customer_id = (res.data or {}).get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(
            status_code=404,
            detail="No billing account found. Subscribe to a plan first.",
        )

    try:
        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=RETURN_URL,
        )
        logger.info(f"[billing] portal session created user={user_id}")
        return {"url": portal.url}
    except stripe.StripeError as e:
        logger.error(f"[billing] portal error user={user_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


# ─── POST /api/billing/webhook ────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint. Must be registered in the Stripe dashboard.
    Verifies the signature using STRIPE_WEBHOOK_SECRET, then handles:

      checkout.session.completed      → set plan + save stripe_customer_id
      customer.subscription.updated   → update plan based on price_id
      customer.subscription.deleted   → downgrade to free
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured.")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.warning(f"[billing/webhook] signature verification failed: {e}")
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    db = get_supabase()
    etype = event["type"]
    obj   = event["data"]["object"]

    # ── checkout.session.completed ─────────────────────────────────────────────
    if etype == "checkout.session.completed":
        user_id     = (obj.get("metadata") or {}).get("user_id")
        price_id    = (obj.get("metadata") or {}).get("price_id")
        customer_id = obj.get("customer")
        plan_name   = _plan_for_price(price_id or "")

        if not user_id or not plan_name:
            logger.warning(f"[billing/webhook] checkout.completed missing metadata user={user_id} price={price_id}")
            return {"ok": True}

        update: dict = {"plan_name": plan_name}
        if customer_id:
            update["stripe_customer_id"] = customer_id
        db.table("user_plans").update(update).eq("user_id", user_id).execute()
        logger.info(f"[billing/webhook] checkout.completed → user={user_id} plan={plan_name}")
        from modules.email.service import notify_admin
        notify_admin(
            subject=f"💰 New Paying Customer — {plan_name}",
            body=f"Someone just upgraded to {plan_name}. Stripe customer: {customer_id}. User ID: {user_id}.",
        )

    # ── customer.subscription.updated ─────────────────────────────────────────
    elif etype == "customer.subscription.updated":
        customer_id = obj.get("customer")
        items = (obj.get("items") or {}).get("data") or []
        price_id  = items[0]["price"]["id"] if items else None
        plan_name = _plan_for_price(price_id or "")

        if customer_id and plan_name:
            db.table("user_plans").update({"plan_name": plan_name}).eq("stripe_customer_id", customer_id).execute()
            logger.info(f"[billing/webhook] subscription.updated customer={customer_id} → plan={plan_name}")
        else:
            logger.warning(f"[billing/webhook] subscription.updated unknown price={price_id} customer={customer_id}")

    # ── customer.subscription.deleted ─────────────────────────────────────────
    elif etype == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        if customer_id:
            db.table("user_plans").update({"plan_name": "free"}).eq("stripe_customer_id", customer_id).execute()
            logger.info(f"[billing/webhook] subscription.deleted customer={customer_id} → free")
            from modules.email.service import notify_admin
            notify_admin(
                subject="❌ Subscription Cancelled",
                body=f"A user cancelled and was downgraded to free. Stripe customer: {customer_id}.",
            )

    else:
        logger.debug(f"[billing/webhook] unhandled event type: {etype}")

    return {"ok": True}
