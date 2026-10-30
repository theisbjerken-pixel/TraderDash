"""Who may open which stocks.

``plan`` is the only subscription value the rest of TraderDash needs.
A later payment system should set this variable. It should not grow its own
stock lists or plan checks.

    plan = "free" | "nordic" | "international"

Nordic includes Free. International includes Nordic and Free.
"""

from __future__ import annotations

import universes

# Development default. Change this while testing, or use the Plan control
# in the sidebar. A subscription system can replace this later.
plan = "free"

PLANS = universes.TIERS

PLAN_LABELS = universes.TIER_LABELS

_COUNTRY_ALIASES = {
    "denmark": "denmark",
    "dk": "denmark",
    "danmark": "denmark",
    "sweden": "sweden",
    "se": "sweden",
    "sverige": "sweden",
    "norway": "norway",
    "no": "norway",
    "norge": "norway",
    "united states": "united states",
    "united states of america": "united states",
    "us": "united states",
    "usa": "united states",
    "united kingdom": "united kingdom",
    "uk": "united kingdom",
    "gb": "united kingdom",
    "great britain": "united kingdom",
    "germany": "germany",
    "de": "germany",
    "deutschland": "germany",
    "tyskland": "germany",
    "france": "france",
    "fr": "france",
    "frankrig": "france",
}


def _require_plan(value: str) -> str:
    key = str(value).strip().lower()
    if key not in PLANS:
        raise ValueError(f"Unknown plan: {value}")
    return key


def _country_name(country: str) -> str | None:
    return _COUNTRY_ALIASES.get(str(country).strip().lower())


def get_allowed_stocks(plan: str) -> dict[str, str]:
    """Ticker to company name for this plan, including every lower plan."""
    return universes.stocks_for(_require_plan(plan))


def can_access(ticker: str, plan: str) -> bool:
    return str(ticker).strip() in get_allowed_stocks(plan)


def can_access_market(country: str, plan: str) -> bool:
    name = _country_name(country)
    if name is None:
        return False
    return name in universes.countries_in(_require_plan(plan))


MARKETS = (
    "denmark",
    "sweden",
    "norway",
    "united states",
    "united kingdom",
    "germany",
    "france",
)

MARKET_LABELS = {
    "denmark": "Denmark",
    "sweden": "Sweden",
    "norway": "Norway",
    "united states": "USA",
    "united kingdom": "United Kingdom",
    "germany": "Germany",
    "france": "France",
}


def market_of(ticker: str) -> str | None:
    return universes.market_of(str(ticker).strip())


def stocks_in_market(country: str) -> dict[str, str]:
    """Every predefined stock in one market, before the plan filter."""
    name = _country_name(country)
    if name is None:
        return {}
    stocks: dict[str, str] = {}
    for group in universes.MARKET_GROUPS.get(name, ()):
        stocks.update(group)
    return stocks


def minimum_plan_for_ticker(ticker: str) -> str | None:
    symbol = str(ticker).strip()
    for key in PLANS:
        if can_access(symbol, key):
            return key
    return None


def minimum_plan_for_market(country: str) -> str | None:
    for key in PLANS:
        if can_access_market(country, key):
            return key
    return None


def upgrade_message(required_plan: str) -> str:
    return f"Available with TraderDash {PLAN_LABELS[_require_plan(required_plan)]}"


def aligned_selection(market: str | None, symbol: str | None, plan: str) -> tuple[str, str]:
    """A country and a stock that belong together.

    An unknown country becomes Denmark. A stock from another country is
    replaced with the first stock in the chosen country that this plan may
    open. A locked stock that does belong to the chosen country is left in
    place, so the paywall can still explain it.
    """
    chosen = market if market in MARKETS else "denmark"
    codes = list(stocks_in_market(chosen))
    if not codes:
        return chosen, ""
    current = str(symbol or "").strip()
    if current in codes:
        return chosen, current
    entitled = [code for code in codes if may_analyse(code, plan, chosen)]
    return chosen, entitled[0] if entitled else codes[0]


def may_analyse(ticker: str, plan: str, market: str | None = None) -> bool:
    """True only when this plan may open this predefined stock.

    A ticker that is not in the plan, not in the catalog, or not in the
    selected market is rejected. Unknown plans are rejected.
    """
    try:
        key = _require_plan(plan)
    except ValueError:
        return False
    symbol = str(ticker).strip()
    if not symbol or not can_access(symbol, key):
        return False
    listed = market_of(symbol)
    if listed is None or not can_access_market(listed, key):
        return False
    if market is not None and _country_name(market) != listed:
        return False
    return True
