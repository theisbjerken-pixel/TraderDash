"""Commercial plan catalogue for the Account page.

Entitlements stay in access.py. This file only describes what the page
shows: names, prices, markets, features and the Stripe Price ID that
checkout can use later. Empty or placeholder price IDs do not start a payment.
"""

from __future__ import annotations

from dataclasses import dataclass

import access

CHECKOUT_UNAVAILABLE = "Secure subscription checkout is not yet activated."

STATUS_LABELS = {
    "free": "Free",
    "active": "Active",
    "trialing": "Trialing",
    "past_due": "Past due",
    "incomplete": "Incomplete",
    "cancelled": "Cancelled",
    "expired": "Expired",
}


@dataclass(frozen=True)
class PlanOffer:
    key: str
    name: str
    price_amount: int
    currency: str
    billing_period: str
    price_note: str
    description: str
    markets: tuple[str, ...]
    features: tuple[str, ...]
    displayed_stock_count: str
    stripe_price_id: str


PLAN_OFFERS: dict[str, PlanOffer] = {
    "free": PlanOffer(
        key="free",
        name="Free",
        price_amount=0,
        currency="DKK",
        billing_period="",
        price_note="",
        description="A focused selection of Nordic stocks, with the full TraderDash analysis.",
        markets=("denmark", "sweden", "norway"),
        features=(
            "approximately 30 selected Nordic stocks",
            "10 Danish stocks",
            "10 Swedish stocks",
            "10 Norwegian stocks",
            "full TraderDash analysis for included stocks",
        ),
        displayed_stock_count="approximately 30",
        stripe_price_id="",
    ),
    "nordic": PlanOffer(
        key="nordic",
        name="Nordic",
        price_amount=39,
        currency="DKK",
        billing_period="month",
        price_note="Temporary test price",
        description="Everything in Free, plus the complete configured Nordic universe.",
        markets=("denmark", "sweden", "norway"),
        features=(
            "everything in Free",
            "the complete configured Nordic stock universe",
            "leading Danish, Swedish and Norwegian stocks",
            "full TraderDash analysis for included stocks",
        ),
        displayed_stock_count="complete Nordic universe",
        stripe_price_id="price_placeholder_nordic",
    ),
    "international": PlanOffer(
        key="international",
        name="International",
        price_amount=79,
        currency="DKK",
        billing_period="month",
        price_note="Temporary test price",
        description="Everything in Nordic, plus stocks in the United States, the United Kingdom, Germany and France.",
        markets=(
            "denmark",
            "sweden",
            "norway",
            "united states",
            "united kingdom",
            "germany",
            "france",
        ),
        features=(
            "everything in Nordic",
            "approximately 140 selected stocks",
            "seven markets: Denmark, Sweden, Norway, United States, United Kingdom, Germany and France",
            "full TraderDash analysis for included stocks",
        ),
        displayed_stock_count="approximately 140",
        stripe_price_id="price_placeholder_international",
    ),
}


def _validate() -> None:
    if tuple(PLAN_OFFERS) != tuple(access.PLANS):
        raise RuntimeError("Plan catalogue does not match the entitlement plans.")
    for key, offer in PLAN_OFFERS.items():
        if offer.key != key or offer.name != access.PLAN_LABELS[key]:
            raise RuntimeError(f"Plan name mismatch for {key}.")
        for market in offer.markets:
            if market not in access.MARKETS:
                raise RuntimeError(f"Unknown market on {key}: {market}")


_validate()


def offers() -> tuple[PlanOffer, ...]:
    return tuple(PLAN_OFFERS[key] for key in access.PLANS)


def price_label(offer: PlanOffer) -> str:
    amount = f"{offer.price_amount} {offer.currency}"
    if offer.billing_period == "month":
        return f"{amount} per month"
    return amount


def relation(active_plan: str, offer: PlanOffer) -> str:
    """How this card relates to the plan the user has right now."""
    active_rank = access.PLANS.index(active_plan)
    offer_rank = access.PLANS.index(offer.key)
    if offer.key == active_plan:
        return "current"
    if offer_rank < active_rank:
        return "included"
    return "upgrade"


def action_label(active_plan: str, offer: PlanOffer) -> str:
    kind = relation(active_plan, offer)
    if kind == "current":
        return "Current plan"
    if kind == "included":
        return "Included in your plan"
    return f"Upgrade to {offer.name}"


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def request_checkout(plan_key: str) -> str:
    """Reserve the checkout call for a later Stripe connection.

    The plan's stripe_price_id is the value that call will send. Until then
    the Account page shows one message, and the account plan stays as it is.
    """
    if plan_key not in PLAN_OFFERS:
        raise KeyError(plan_key)
    return CHECKOUT_UNAVAILABLE
