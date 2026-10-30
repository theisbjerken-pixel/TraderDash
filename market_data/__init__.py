"""Market data used by TraderDash.

Analysis and the interface call these functions. They do not choose a vendor.
The current vendor is Yahoo Finance, implemented in yfinance_provider.py.
"""

from market_data.freshness import MarketDataStatus, describe_freshness
from market_data.yfinance_provider import get_fundamentals, get_history, get_price, get_quote

__all__ = [
    "MarketDataStatus",
    "describe_freshness",
    "get_fundamentals",
    "get_history",
    "get_price",
    "get_quote",
]
