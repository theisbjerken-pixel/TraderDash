"""How old the latest market data is.

A later vendor can set ``status`` to real-time, delayed or end-of-day.
The current Yahoo data does not prove a real-time feed, so that status
is left unset unless the provider itself reports a delay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo

import pandas as pd

DISPLAY_ZONE = ZoneInfo("Europe/Copenhagen")

_MONTHS = (
    "jan.",
    "feb.",
    "mar.",
    "apr.",
    "maj",
    "jun.",
    "jul.",
    "aug.",
    "sep.",
    "okt.",
    "nov.",
    "dec.",
)


class MarketDataStatus(str, Enum):
    REAL_TIME = "real_time"
    DELAYED = "delayed"
    END_OF_DAY = "end_of_day"


@dataclass(frozen=True)
class MarketDataFreshness:
    updated_at: datetime | None
    status: MarketDataStatus | None = None
    delay_minutes: int | None = None

    def caption(self, now: datetime | None = None) -> str | None:
        if self.updated_at is None:
            return None
        local = self.updated_at.astimezone(DISPLAY_ZONE)
        zone = local.tzname() or "CET"
        clock = not (local.hour == 0 and local.minute == 0 and local.second == 0)
        current = (now or datetime.now(DISPLAY_ZONE)).astimezone(DISPLAY_ZONE)
        if clock and local.date() == current.date():
            when = f"{local:%H:%M} {zone}"
        elif clock:
            when = f"{_date(local)}, {local:%H:%M} {zone}"
        else:
            when = _date(local)
        text = f"Kursdata opdateret: {when}"
        if self.status is MarketDataStatus.DELAYED and self.delay_minutes:
            text += f" · forsinket {self.delay_minutes} min"
        elif self.status is MarketDataStatus.DELAYED:
            text += " · forsinket"
        elif self.status is MarketDataStatus.END_OF_DAY:
            text += " · seneste dagskurs"
        elif self.status is MarketDataStatus.REAL_TIME:
            text += " · realtid"
        return text


def _date(moment: datetime) -> str:
    return f"{moment.day}. {_MONTHS[moment.month - 1]} {moment.year}"


def coerce_timestamp(value: object) -> datetime | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)):
        moment = datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        try:
            parsed = pd.Timestamp(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed):
            return None
        moment = parsed.to_pydatetime()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def freshness_from_provider(
    regular_market_time: object,
    delay_minutes: object,
    granularity: object,
    last_bar: object,
) -> MarketDataFreshness:
    """Build freshness without treating Yahoo as a real-time source.

    A positive delay reported by the provider is delayed. A daily bar with
    no clock time is the latest daily close. Anything else stays unlabeled.
    """
    updated = coerce_timestamp(regular_market_time)
    date_only = False
    if updated is None:
        updated = coerce_timestamp(last_bar)
        date_only = updated is not None
    reported_delay = delay_minutes if isinstance(delay_minutes, int) and not isinstance(delay_minutes, bool) else None
    if isinstance(delay_minutes, float) and delay_minutes == int(delay_minutes):
        reported_delay = int(delay_minutes)
    bar_size = str(granularity or "")
    status = None
    if reported_delay is not None and reported_delay > 0:
        status = MarketDataStatus.DELAYED
    elif date_only and bar_size in {"1d", "5d", "1wk", "1mo", "3mo"}:
        status = MarketDataStatus.END_OF_DAY
    return MarketDataFreshness(updated_at=updated, status=status, delay_minutes=reported_delay)


def describe_freshness(history: pd.DataFrame, now: datetime | None = None) -> str | None:
    freshness = history.attrs.get("market_data_freshness")
    if not isinstance(freshness, MarketDataFreshness):
        return None
    return freshness.caption(now)
