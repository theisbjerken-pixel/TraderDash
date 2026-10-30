"""Yahoo Finance provider.

This is the only module that talks to yfinance. Replace this file to switch
market-data vendor. Callers should use market_data.get_history, get_quote,
get_fundamentals and get_price.

Successful history and quote responses are cached for five minutes and shared
by every caller in this process. A failed request is remembered for one minute
and is not retried. Each Yahoo call waits at most REQUEST_TIMEOUT_SECONDS.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

try:
    yf.config.network.retries = 0
except Exception:
    pass

from market_data.cache import cached_history, get_or_load
from market_data.freshness import freshness_from_provider

REQUEST_TIMEOUT_SECONDS = 8

FUNDAMENTAL_FIELDS = (
    "trailing_pe",
    "forward_pe",
    "price_to_sales",
    "price_to_book",
    "dividend_yield",
    "dividend_growth_5y",
    "payout_ratio",
)

_HISTORY_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

_TIMEOUT_MESSAGE = "Kursdata svarede ikke i tide. Prøv igen om et øjeblik."
_RATE_LIMIT_MESSAGE = "For mange opslag hos kurskilden lige nu. Vent et øjeblik, og prøv igen."
_UNAVAILABLE_MESSAGE = "Kursdata er midlertidigt utilgængelige. Prøv igen om et øjeblik."


def _optional_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _dividend_yield_ratio(info: dict) -> float | None:
    trailing = _optional_float(info.get("trailingAnnualDividendYield"))
    if trailing is not None:
        return trailing
    stated = _optional_float(info.get("dividendYield"))
    if stated is None:
        return None
    return stated / 100 if stated > 1 else stated


def _annual_dividend_growth(dividends: pd.Series, years: int = 5) -> float | None:
    if dividends is None or len(dividends) < 2:
        return None
    amounts = dividends.dropna()
    if amounts.empty:
        return None
    counts = amounts.groupby(amounts.index.year).size()
    totals = amounts.groupby(amounts.index.year).sum().sort_index()
    if len(counts) > 1 and counts.iloc[-1] < counts.iloc[:-1].median():
        totals = totals.iloc[:-1]
    if len(totals) < 2:
        return None
    end_year = int(totals.index[-1])
    start_year = end_year - years
    if start_year not in totals.index:
        return None
    start = float(totals.loc[start_year])
    end = float(totals.loc[end_year])
    if start <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _run_with_timeout(func):
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func)
    try:
        return future.result(REQUEST_TIMEOUT_SECONDS)
    except FuturesTimeoutError as exc:
        raise TimeoutError(_TIMEOUT_MESSAGE) from exc
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _empty_history(message: str | None) -> pd.DataFrame:
    frame = pd.DataFrame()
    if message:
        frame.attrs["market_data_error"] = message
    return frame


def _copy_history(frame: pd.DataFrame) -> pd.DataFrame:
    copied = frame.copy(deep=True)
    copied.attrs = dict(frame.attrs)
    return copied


def _blank_quote(message: str | None = None) -> dict:
    quote = {
        "bid": None,
        "ask": None,
        "bid_size": 0.0,
        "ask_size": 0.0,
        "trailing_pe": None,
        "forward_pe": None,
        "price_to_sales": None,
        "price_to_book": None,
        "dividend_yield": None,
        "dividend_growth_5y": None,
        "payout_ratio": None,
    }
    if message:
        quote["_notice"] = message
    return quote


def _message_for(exc: Exception) -> str:
    if isinstance(exc, YFRateLimitError):
        return _RATE_LIMIT_MESSAGE
    if isinstance(exc, TimeoutError):
        return _TIMEOUT_MESSAGE
    text = str(exc).lower()
    if "429" in text or "rate limit" in text or "too many" in text:
        return _RATE_LIMIT_MESSAGE
    if "timeout" in text or "timed out" in text:
        return _TIMEOUT_MESSAGE
    return _UNAVAILABLE_MESSAGE


def _load_history(ticker: str, period: str) -> tuple[pd.DataFrame, bool]:
    def fetch() -> tuple[pd.DataFrame, dict]:
        source = yf.Ticker(ticker)
        history = source.history(
            period=period,
            auto_adjust=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
            raise_errors=True,
        )
        meta = getattr(source, "history_metadata", None) or {}
        return history, dict(meta)

    try:
        history, meta = _run_with_timeout(fetch)
    except Exception as exc:
        return _empty_history(_message_for(exc)), True
    if history is None or history.empty:
        return _empty_history(None), False
    history = history.rename(columns=str.title)
    missing = [column for column in _HISTORY_COLUMNS if column not in history.columns]
    if missing:
        return _empty_history(None), False
    history = history[_HISTORY_COLUMNS].dropna()
    last_bar = history.index[-1] if not history.empty else None
    history.attrs["market_data_freshness"] = freshness_from_provider(
        meta.get("regularMarketTime"),
        meta.get("exchangeDataDelayedBy"),
        meta.get("dataGranularity"),
        last_bar,
    )
    return history, False


def _build_quote(info: dict, dividends: pd.Series) -> dict:
    bid = info.get("bid")
    ask = info.get("ask")
    return {
        "bid": float(bid) if bid else None,
        "ask": float(ask) if ask else None,
        "bid_size": float(info.get("bidSize") or 0),
        "ask_size": float(info.get("askSize") or 0),
        "trailing_pe": _optional_float(info.get("trailingPE")),
        "forward_pe": _optional_float(info.get("forwardPE")),
        "price_to_sales": _optional_float(info.get("priceToSalesTrailing12Months")),
        "price_to_book": _optional_float(info.get("priceToBook")),
        "dividend_yield": _dividend_yield_ratio(info),
        "dividend_growth_5y": _annual_dividend_growth(dividends),
        "payout_ratio": _optional_float(info.get("payoutRatio")),
    }


def _load_quote(ticker: str) -> tuple[dict, bool]:
    ticker_obj = yf.Ticker(ticker)
    try:
        info = _run_with_timeout(lambda: ticker_obj.info or {})
    except Exception as exc:
        return _blank_quote(_message_for(exc)), True
    if not isinstance(info, dict):
        info = {}
    try:
        dividends = _run_with_timeout(lambda: ticker_obj.dividends)
    except Exception:
        dividends = pd.Series(dtype=float)
    if dividends is None:
        dividends = pd.Series(dtype=float)
    return _build_quote(info, dividends), False


def get_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    frame = get_or_load(
        ("history", ticker, period),
        lambda: _load_history(ticker, period),
        REQUEST_TIMEOUT_SECONDS + 1,
        lambda: _empty_history(_TIMEOUT_MESSAGE),
    )
    return _copy_history(frame)


def get_quote(ticker: str) -> dict:
    quote = get_or_load(
        ("quote", ticker),
        lambda: _load_quote(ticker),
        REQUEST_TIMEOUT_SECONDS + 1,
        lambda: _blank_quote(_TIMEOUT_MESSAGE),
    )
    return dict(quote)


def get_fundamentals(ticker: str) -> dict:
    quote = get_quote(ticker)
    return {field: quote[field] for field in FUNDAMENTAL_FIELDS}


def get_price(ticker: str) -> float | None:
    history = cached_history(ticker)
    if history is None:
        history = get_history(ticker, period="5d")
    if history is None or history.empty or "Close" not in history:
        return None
    close = history["Close"].dropna()
    if close.empty:
        return None
    return float(close.iloc[-1])


__all__ = [
    "REQUEST_TIMEOUT_SECONDS",
    "get_fundamentals",
    "get_history",
    "get_price",
    "get_quote",
]
