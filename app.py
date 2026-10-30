"""TraderDash: kursgraf og nøgletal til portefølje og daytrading."""

import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import access
import account_page
import accounts
from market_data import describe_freshness, get_history, get_quote

TRADING_DAYS = 252
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

st.set_page_config(
    page_title="TraderDash",
    page_icon="📈",
    layout="wide",
    menu_items={
        "About": "TraderDash viser signaler og overblik for de aktier, der følger med din plan.",
    },
)


def rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    relative_strength = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + relative_strength))


def macd(close: pd.Series) -> pd.DataFrame:
    fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    line = fast - slow
    signal = line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    return pd.DataFrame({"macd": line, "signal": signal, "histogram": line - signal})


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float) -> float:
    excess = returns - (risk_free_rate / TRADING_DAYS)
    volatility = excess.std()
    if volatility == 0 or np.isnan(volatility):
        return float("nan")
    return float((excess.mean() / volatility) * np.sqrt(TRADING_DAYS))


SIGNAL_COLORS = {
    "KØB": {"bg": "#dcfce7", "fg": "#14532d", "bar": "#16a34a"},
    "SÆLG": {"bg": "#fee2e2", "fg": "#7f1d1d", "bar": "#dc2626"},
    "AFVENT": {"bg": "#fef3c7", "fg": "#78350f", "bar": "#d97706"},
    "KURS": {"bg": "#e0f2fe", "fg": "#0c4a6e", "bar": "#0284c7"},
    "FAKTA": {"bg": "#f1f5f9", "fg": "#0f172a", "bar": "#64748b"},
}


def rsi_signal(value: float) -> tuple[str, str]:
    if value >= 70:
        return "SÆLG", f"RSI {value:.1f} · over 70"
    if value <= 30:
        return "KØB", f"RSI {value:.1f} · under 30"
    return "AFVENT", f"RSI {value:.1f} · mellem 30 og 70"


def macd_signal(indicator: pd.DataFrame) -> tuple[str, str]:
    previous = indicator.iloc[-2]
    latest = indicator.iloc[-1]
    crossed_up = previous["macd"] <= previous["signal"] and latest["macd"] > latest["signal"]
    crossed_down = previous["macd"] >= previous["signal"] and latest["macd"] < latest["signal"]
    if crossed_up:
        return "KØB", f"{latest['macd']:.3f} · krydsede op"
    if crossed_down:
        return "SÆLG", f"{latest['macd']:.3f} · krydsede ned"
    if latest["macd"] > latest["signal"]:
        return "KØB", f"{latest['macd']:.3f} · over signallinjen"
    if latest["macd"] < latest["signal"]:
        return "SÆLG", f"{latest['macd']:.3f} · under signallinjen"
    return "AFVENT", "Ligger på signallinjen"


def combined_signal(rsi_action: str, macd_action: str, macd_detail: str) -> tuple[str, str]:
    fresh_cross = "krydsede" in macd_detail
    if rsi_action == macd_action and rsi_action in {"KØB", "SÆLG"}:
        return rsi_action, "RSI og MACD er enige"
    if fresh_cross and rsi_action != opposite_action(macd_action):
        return macd_action, "Nyt MACD-kryds"
    if {rsi_action, macd_action} == {"KØB", "SÆLG"}:
        return "AFVENT", "RSI og MACD er uenige"
    return "AFVENT", "RSI er ikke i zone"


def opposite_action(action: str) -> str:
    return {"KØB": "SÆLG", "SÆLG": "KØB"}.get(action, "AFVENT")


def portfolio_signal(volatility: float, sharpe: float) -> tuple[str, str]:
    stats = f"Vol {volatility:.0%} · Sharpe {sharpe:.2f}"
    if sharpe >= 1 and volatility <= 0.25:
        return "KØB", stats
    if sharpe < 0 or volatility >= 0.40:
        return "SÆLG", stats
    return "AFVENT", stats


def trend_signal(close: pd.Series) -> tuple[str, str]:
    if len(close) < 50:
        return "AFVENT", "Kræver mindst 50 dage"
    sma_fast = close.rolling(20).mean().iloc[-1]
    sma_slow = close.rolling(50).mean().iloc[-1]
    price = close.iloc[-1]
    if price > sma_fast > sma_slow:
        return "KØB", "Kurs over SMA 20 og 50"
    if price < sma_fast < sma_slow:
        return "SÆLG", "Kurs under SMA 20 og 50"
    return "AFVENT", "SMA 20 og 50 er uenige"


def bollinger_bands(close: pd.Series, window: int = 20, deviations: float = 2) -> pd.DataFrame:
    mid = close.rolling(window).mean()
    width = close.rolling(window).std()
    return pd.DataFrame({"mid": mid, "upper": mid + deviations * width, "lower": mid - deviations * width})


def bollinger_signal(close: pd.Series) -> tuple[str, str]:
    if len(close) < 20:
        return "AFVENT", "Kræver mindst 20 dage"
    bands = bollinger_bands(close)
    price = float(close.iloc[-1])
    if price >= float(bands["upper"].iloc[-1]):
        return "SÆLG", "Ved øvre bånd"
    if price <= float(bands["lower"].iloc[-1]):
        return "KØB", "Ved nedre bånd"
    return "AFVENT", "Inde i båndet"


def volume_signal(history: pd.DataFrame) -> tuple[str, str]:
    average = history["Volume"].rolling(20).mean().iloc[-1]
    latest = history["Volume"].iloc[-1]
    if pd.isna(average) or average == 0:
        return "AFVENT", "For lidt volumen"
    ratio = float(latest / average)
    day_change = float(history["Close"].iloc[-1] / history["Close"].iloc[-2] - 1)
    detail = f"{ratio:.1f}x snitvolumen"
    if ratio >= 1.5 and day_change > 0:
        return "KØB", detail
    if ratio >= 1.5 and day_change < 0:
        return "SÆLG", detail
    return "AFVENT", detail


def momentum_signal(close: pd.Series) -> tuple[str, str]:
    if len(close) < 11:
        return "AFVENT", "For kort periode"
    change = float(close.iloc[-1] / close.iloc[-11] - 1)
    detail = f"10 dage {change:+.1%}"
    if change >= 0.03:
        return "KØB", detail
    if change <= -0.03:
        return "SÆLG", detail
    return "AFVENT", detail


def stochastic_signal(history: pd.DataFrame) -> tuple[str, str]:
    low = history["Low"].rolling(14).min()
    high = history["High"].rolling(14).max()
    span = high.iloc[-1] - low.iloc[-1]
    if pd.isna(span) or span == 0:
        return "AFVENT", "For kort periode"
    value = float(100 * (history["Close"].iloc[-1] - low.iloc[-1]) / span)
    if value >= 80:
        return "SÆLG", f"%K {value:.0f} · over 80"
    if value <= 20:
        return "KØB", f"%K {value:.0f} · under 20"
    return "AFVENT", f"%K {value:.0f} · mellem 20 og 80"


def depth_signal(bid_size: float, ask_size: float) -> tuple[str, str]:
    if bid_size <= 0 and ask_size <= 0:
        return "AFVENT", "Ingen størrelse fra børsen"
    total = bid_size + ask_size
    detail = f"Bud {bid_size:,.0f} · udbud {ask_size:,.0f}"
    if bid_size / total >= 0.6:
        return "KØB", detail
    if ask_size / total >= 0.6:
        return "SÆLG", detail
    return "AFVENT", detail


METRIC_HELP = {
    "Handel": "Samlet signal ud fra RSI og MACD. Køb eller sælg når de peger samme vej. Afvent når de er uenige, eller når RSI ligger mellem 30 og 70.",
    "RSI": "Relative Strength Index over 14 dage. Måler om kursen er steget eller faldet kraftigt. Over 70 er overkøbt og giver sælg. Under 30 er oversolgt og giver køb.",
    "MACD": "Forskellen mellem et 12-dages og et 26-dages glidende gennemsnit, holdt op mod en signallinje på 9 dage. Køb når MACD er over signallinjen. Sælg når den er under.",
    "Portefølje": "Risikojusteret afkast ud fra Sharpe og årlig volatilitet. Køb ved Sharpe mindst 1 og volatilitet højst 25 %. Sælg ved negativ Sharpe eller volatilitet mindst 40 %.",
    "Bud": "Den højeste pris en køber vil betale lige nu.",
    "Udbud": "Den laveste pris en sælger vil acceptere lige nu. Spread er forskellen mellem udbud og bud.",
    "Dybde": "Hvor mange aktier der ligger i bud og udbud. Køb når buddet er mindst 60 % af mængden. Sælg når udbuddet er mindst 60 %.",
    "Trend": "Retning ud fra glidende gennemsnit. Køb når kursen er over både 20- og 50-dages snit, og 20-dages snit er over 50-dages. Sælg når det er omvendt.",
    "Bollinger": "Bånd omkring 20-dages gennemsnit, to standardafvigelser ude. Sælg når kursen rører det øvre bånd. Køb når den rører det nedre.",
    "Volumen": "Dagens handel i forhold til gennemsnittet de seneste 20 dage. Mindst 1,5 gange snittet på en opdag er køb. Samme niveau på en neddag er sælg.",
    "Momentum": "Kursændring over de seneste 10 dage. Køb ved mindst 3 % stigning. Sælg ved mindst 3 % fald.",
    "Stokastisk": "Hvor lukkekursen ligger i de seneste 14 dages interval. Over 80 er overkøbt og giver sælg. Under 20 er oversolgt og giver køb.",
    "P/E": "Kurs divideret med indtjening de seneste 12 måneder. Et lavt tal betyder, at du betaler mindre for hver krone selskabet har tjent.",
    "P/FE": "Kurs divideret med den forventede indtjening. Viser prisen i forhold til analytikernes estimat for den kommende indtjening.",
    "P/S": "Kurs divideret med omsætning. Bruges når indtjeningen svinger, eller selskabet ikke har overskud.",
    "P/B": "Kurs divideret med bogført egenkapital pr. aktie. Under 1 betyder, at aktien handles under den bogførte værdi.",
    "Udbytte": "Udbytteprocent. Det seneste års udbytte i forhold til kursen. 4 % betyder, at udbyttet svarer til 4 % af den aktuelle kurs.",
    "Vækst 5 år": "Udbyttevækst de seneste 5 år. Den årlige vækst i udbetalt udbytte pr. aktie, fra udbyttet fem år tidligere til det seneste hele år.",
    "Payout": "Payout ratio. Den andel af indtjeningen der udbetales som udbytte. 45 % betyder, at selskabet udlodder 45 øre af hver tjent krone.",
}


def signal_card(title: str, action: str, detail: str, tone: str | None = None) -> str:
    color = SIGNAL_COLORS[tone or action]
    help_text = html.escape(METRIC_HELP[title])
    return (
        f'<div style="position:relative;background:{color["bg"]};color:{color["fg"]};border-radius:8px;'
        f'padding:6px 22px 6px 10px;border-left:4px solid {color["bar"]};'
        f'box-sizing:border-box;height:100%;">'
        f'<span class="td-help">?<span class="td-tip">{help_text}</span></span>'
        f'<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.04em;line-height:1.15;">{html.escape(title.upper())}</div>'
        f'<div style="font-size:0.95rem;font-weight:800;line-height:1.15;margin:1px 0;">{html.escape(action)}</div>'
        f'<div style="font-size:0.72rem;line-height:1.25;min-height:2.5em;">{html.escape(detail)}</div>'
        f"</div>"
    )


def load_history(symbol: str, period: str) -> pd.DataFrame:
    return get_history(symbol, period)


def load_quote(symbol: str) -> dict:
    return get_quote(symbol)


def _fetch_notice(history: pd.DataFrame, quote: dict | None = None) -> str | None:
    notice = history.attrs.get("market_data_error")
    if notice:
        return str(notice)
    if quote:
        quote_notice = quote.get("_notice")
        if quote_notice:
            return str(quote_notice)
    return None


def format_multiple(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}"


def format_percent(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:+.1%}" if signed else f"{value:.1%}"


def fundamental_cards(quote: dict) -> list[tuple[str, str, str, str | None]]:
    return [
        ("P/E", format_multiple(quote.get("trailing_pe")), "Kurs / indtjening", "FAKTA"),
        ("P/FE", format_multiple(quote.get("forward_pe")), "Forward indtjening", "FAKTA"),
        ("P/S", format_multiple(quote.get("price_to_sales")), "Kurs / omsætning", "FAKTA"),
        ("P/B", format_multiple(quote.get("price_to_book")), "Kurs / bogført værdi", "FAKTA"),
        ("Udbytte", format_percent(quote.get("dividend_yield")), "Udbytteprocent", "FAKTA"),
        ("Vækst 5 år", format_percent(quote.get("dividend_growth_5y"), signed=True), "Årlig udbyttevækst", "FAKTA"),
        ("Payout", format_percent(quote.get("payout_ratio")), "Andel af indtjeningen", "FAKTA"),
    ]


DIRECTIONAL_SIGNALS = (
    "RSI",
    "MACD",
    "Portefølje",
    "Dybde",
    "Trend",
    "Bollinger",
    "Volumen",
    "Momentum",
    "Stokastisk",
)


def card_grid(cards: list[tuple[str, str, str, str | None]]) -> str:
    cells = "".join(signal_card(title, action, detail, tone) for title, action, detail, tone in cards)
    return (
        '<div style="display:grid;grid-template-columns:repeat(4,minmax(0,1fr));'
        'gap:10px;align-items:stretch;">'
        f"{cells}</div>"
    )


def render_split_cards(
    trading: list[tuple[str, str, str, str | None]],
    fundamentals: list[tuple[str, str, str, str | None]],
) -> None:
    st.html(
        "<style>"
        ".td-help{position:absolute;top:5px;right:6px;width:14px;height:14px;border:1px solid currentColor;"
        "border-radius:50%;font-size:10px;font-weight:700;line-height:12px;text-align:center;letter-spacing:0;"
        "opacity:0.75;cursor:help;z-index:2;}"
        ".td-help .td-tip{display:none;position:absolute;top:18px;right:0;width:230px;padding:8px 10px;"
        "background:#0f172a;color:#f8fafc;border-radius:6px;font-size:0.72rem;font-weight:500;line-height:1.35;"
        "letter-spacing:0;text-align:left;white-space:normal;z-index:30;"
        "box-shadow:0 8px 18px rgba(15,23,42,0.22);}"
        ".td-help:hover{opacity:1;z-index:31;}"
        ".td-help:hover .td-tip{display:block;}"
        "</style>"
        '<div style="display:flex;flex-direction:column;gap:10px;">'
        f"{card_grid(trading)}"
        '<div style="border-top:1px dashed #94a3b8;"></div>'
        f"{card_grid(fundamentals)}"
        "</div>"
    )


def signal_snapshot(history: pd.DataFrame, quote: dict, risk_free_rate: float) -> dict:
    close = history["Close"]
    daily_returns = close.pct_change().dropna()
    indicator_rsi = rsi(close)
    indicator_macd = macd(close)
    latest_rsi = float(indicator_rsi.dropna().iloc[-1])
    volatility = annualized_volatility(daily_returns)
    sharpe = sharpe_ratio(daily_returns, risk_free_rate)
    last_price = float(close.iloc[-1])
    change = float(close.iloc[-1] / close.iloc[0] - 1)

    rsi_action, rsi_detail = rsi_signal(latest_rsi)
    macd_action, macd_detail = macd_signal(indicator_macd)
    headline_action, headline_detail = combined_signal(rsi_action, macd_action, macd_detail)
    risk_action, risk_detail = portfolio_signal(volatility, sharpe)
    headline_detail = f"{headline_detail} · {last_price:,.2f} ({change:+.1%})"

    bid_text = f"{quote['bid']:,.2f}" if quote.get("bid") else "—"
    ask_text = f"{quote['ask']:,.2f}" if quote.get("ask") else "—"
    if quote.get("bid") and quote.get("ask"):
        spread = quote["ask"] - quote["bid"]
        bid_detail = "Bedste køber"
        ask_detail = f"Spread {spread:.2f}"
    else:
        bid_detail = "Ikke offentliggjort"
        ask_detail = "Ikke offentliggjort"
    depth_action, depth_detail = depth_signal(quote.get("bid_size") or 0, quote.get("ask_size") or 0)

    cards = [
        ("Handel", headline_action, headline_detail, None),
        ("RSI", rsi_action, rsi_detail, None),
        ("MACD", macd_action, macd_detail, None),
        ("Portefølje", risk_action, risk_detail, None),
        ("Bud", bid_text, bid_detail, "KURS"),
        ("Udbud", ask_text, ask_detail, "KURS"),
        ("Dybde", depth_action, depth_detail, None),
        ("Trend", *trend_signal(close), None),
        ("Bollinger", *bollinger_signal(close), None),
        ("Volumen", *volume_signal(history), None),
        ("Momentum", *momentum_signal(close), None),
        ("Stokastisk", *stochastic_signal(history), None),
    ]
    counted = [card for card in cards if card[0] in DIRECTIONAL_SIGNALS]
    buys = [title for title, action, _, _ in counted if action == "KØB"]
    sells = [title for title, action, _, _ in counted if action == "SÆLG"]
    waits = [title for title, action, _, _ in counted if action == "AFVENT"]
    net = len(buys) - len(sells)
    if net >= 2:
        stance = "LONG"
    elif net <= -2:
        stance = "SHORT"
    else:
        stance = "NEUTRAL"
    return {
        "price": last_price,
        "change": change,
        "cards": cards,
        "rsi": indicator_rsi,
        "macd": indicator_macd,
        "buys": buys,
        "sells": sells,
        "waits": waits,
        "stance": stance,
        "headline": headline_action,
    }


def manager_assessment(name: str, symbol: str, snapshot: dict) -> str:
    buys = snapshot["buys"]
    sells = snapshot["sells"]
    waits = snapshot["waits"]
    stance = snapshot["stance"]
    buy_text = ", ".join(buys) if buys else "ingen"
    sell_text = ", ".join(sells) if sells else "ingen"
    if stance == "LONG":
        conclusion = "LONG. Flest nøgletal peger på køb, så vurderingen er en lang position."
    elif stance == "SHORT":
        conclusion = "SHORT. Flest nøgletal peger på salg, så vurderingen er en kort position."
    else:
        conclusion = "NEUTRAL. Køb og salg udligner hinanden, så der åbnes ingen position."
    conflict = ""
    if snapshot["headline"] == "KØB" and stance == "SHORT":
        conflict = " Det samlede handelssignal siger køb, men flertallet af nøgletallene siger salg."
    elif snapshot["headline"] == "SÆLG" and stance == "LONG":
        conflict = " Det samlede handelssignal siger salg, men flertallet af nøgletallene siger køb."
    return (
        f"{conclusion}{conflict} {name} ({symbol}) handles til {snapshot['price']:,.2f} "
        f"({snapshot['change']:+.1%} i perioden). "
        f"{len(buys)} køb ({buy_text}) og {len(sells)} salg ({sell_text}). "
        f"{len(waits)} signaler siger afvent."
    )


def paint_watch_row(row: pd.Series) -> list[str]:
    colors = {
        "LONG": "background-color: #dcfce7; color: #14532d",
        "SHORT": "background-color: #fee2e2; color: #7f1d1d",
        "NEUTRAL": "background-color: #fef3c7; color: #78350f",
    }
    style = colors.get(row["Retning"], "background-color: #f1f5f9; color: #334155")
    return [style] * len(row)


def build_chart(history: pd.DataFrame, indicator_rsi: pd.Series, indicator_macd: pd.DataFrame, symbol: str) -> go.Figure:
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.22, 0.23],
        subplot_titles=(
            f"{symbol} kurs",
            "RSI (14) · over 70 overkøbt, under 30 oversolgt",
            "MACD (12, 26, 9)",
        ),
    )

    bands = bollinger_bands(history["Close"])
    band_line = {"color": "#64748b", "width": 1}
    figure.add_trace(
        go.Scatter(x=bands.index, y=bands["lower"], name="Nedre bånd", line=band_line, showlegend=False),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=bands.index,
            y=bands["upper"],
            name="Bollinger (20, 2)",
            line=band_line,
            fill="tonexty",
            fillcolor="rgba(100,116,139,0.14)",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=bands.index,
            y=bands["mid"],
            name="Bollinger midt",
            line={"color": "#64748b", "width": 1, "dash": "dot"},
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Candlestick(
            x=history.index,
            open=history["Open"],
            high=history["High"],
            low=history["Low"],
            close=history["Close"],
            name="Kurs",
            increasing_line_color="#16a34a",
            decreasing_line_color="#dc2626",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=indicator_rsi.index, y=indicator_rsi, name="RSI", line={"color": "#2563eb", "width": 1.6}),
        row=2,
        col=1,
    )
    figure.add_hline(y=70, line_dash="dot", line_color="#dc2626", row=2, col=1)
    figure.add_hline(y=30, line_dash="dot", line_color="#16a34a", row=2, col=1)
    for text, level, color in (
        ("Overkøbt · sælg", 85, "#dc2626"),
        ("Afvent", 50, "#d97706"),
        ("Oversolgt · køb", 15, "#16a34a"),
    ):
        figure.add_annotation(
            text=text,
            x=0.012,
            y=level,
            xref="x2 domain",
            yref="y2",
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font={"size": 11, "color": color},
            bgcolor="rgba(255,255,255,0.82)",
        )

    colors = np.where(indicator_macd["histogram"] >= 0, "#16a34a", "#dc2626")
    figure.add_trace(
        go.Bar(x=indicator_macd.index, y=indicator_macd["histogram"], name="Histogram", marker_color=colors),
        row=3,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=indicator_macd.index, y=indicator_macd["macd"], name="MACD", line={"color": "#0f172a", "width": 1.4}),
        row=3,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=indicator_macd.index, y=indicator_macd["signal"], name="Signal", line={"color": "#f59e0b", "width": 1.4}),
        row=3,
        col=1,
    )

    figure.update_layout(
        height=820,
        margin={"l": 16, "r": 16, "t": 48, "b": 16},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    figure.update_yaxes(title_text="Pris", row=1, col=1)
    figure.update_yaxes(range=[0, 100], row=2, col=1)
    return figure


def _clear_user_session(*, logout: bool) -> None:
    for key in [key for key in st.session_state if str(key).startswith("selected_symbol")]:
        del st.session_state[key]
    for key in ("selected_market", "dev_plan", "plan", "watch_ready", "main_view", "checkout_notice"):
        st.session_state.pop(key, None)
    if logout:
        st.session_state.pop("auth_user_id", None)


def _logout() -> None:
    st.session_state["_pending_logout"] = True
    st.rerun()


def render_account_gate() -> None:
    login_tab, register_tab = st.tabs(["Log ind", "Opret konto"])
    with login_tab:
        with st.form("login"):
            email = st.text_input("E-mail", key="login_email")
            password = st.text_input("Adgangskode", type="password", key="login_password")
            submitted = st.form_submit_button("Log ind", type="primary")
        if submitted:
            try:
                user = accounts.authenticate(email, password)
            except accounts.AccountConfigError as exc:
                st.error(str(exc))
            else:
                if user is None:
                    st.error("Forkert e-mail eller adgangskode.")
                else:
                    _clear_user_session(logout=False)
                    st.session_state.auth_user_id = user.user_id
                    st.rerun()
    with register_tab:
        with st.form("register"):
            email = st.text_input("E-mail", key="register_email")
            password = st.text_input("Adgangskode", type="password", key="register_password")
            confirmation = st.text_input("Gentag adgangskode", type="password", key="register_confirmation")
            submitted = st.form_submit_button("Opret konto", type="primary")
        if submitted:
            if password != confirmation:
                st.error("Adgangskoderne er ikke ens.")
            else:
                try:
                    user = accounts.create_user(email, password)
                except accounts.AccountConfigError as exc:
                    st.error(str(exc))
                except accounts.AccountError as exc:
                    st.error(str(exc))
                else:
                    _clear_user_session(logout=False)
                    st.session_state.auth_user_id = user.user_id
                    st.rerun()


st.title("TraderDash")
st.caption("Enkelt aktie med signaler, eller et farvet overblik over en hel liste.")

for obsolete_key in [key for key in st.session_state if key == "stock_book" or key == "pending_symbol" or str(key).startswith("liste_")]:
    del st.session_state[obsolete_key]
for query_key in ("ticker", "symbol", "stock", "code", "user", "user_id", "plan"):
    if query_key in st.query_params:
        del st.query_params[query_key]

if st.session_state.pop("_pending_logout", False):
    _clear_user_session(logout=True)

try:
    signed_in = accounts.get_user(str(st.session_state.get("auth_user_id") or ""))
except accounts.AccountConfigError as exc:
    st.error(str(exc))
    st.stop()
if signed_in is None:
    _clear_user_session(logout=True)
    render_account_gate()
    st.stop()

with st.sidebar:
    st.header("Opslag")
    st.radio(
        "Side",
        options=("analysis", "account"),
        format_func=lambda value: "Analyse" if value == "analysis" else "Konto",
        key="main_view",
    )
    period = st.selectbox(
        "Periode",
        options=["1mo", "3mo", "6mo", "1y", "2y", "5y"],
        index=3,
        format_func=lambda value: {"1mo": "1 måned", "3mo": "3 måneder", "6mo": "6 måneder", "1y": "1 år", "2y": "2 år", "5y": "5 år"}[value],
    )
    risk_free_pct = st.slider("Risikofri rente (%)", min_value=0.0, max_value=8.0, value=2.0, step=0.5)
    risk_free_rate = risk_free_pct / 100
    st.caption("Perioden og renten bruges både på enkeltaktien og i watchlisten.")
    if accounts.developer_override_enabled():
        if st.session_state.get("dev_plan") not in access.PLANS:
            st.session_state.dev_plan = accounts.resolve_plan(signed_in.plan)
        st.selectbox(
            "Plan",
            options=list(access.PLANS),
            format_func=lambda key: access.PLAN_LABELS[key],
            key="dev_plan",
        )
        st.caption("Udviklertest. Kontoens plan ændres ikke.")
        plan = accounts.resolve_plan(signed_in.plan, st.session_state.get("dev_plan"))
    else:
        plan = accounts.resolve_plan(signed_in.plan, st.session_state.get("plan"))
        st.caption(f"Plan: {access.PLAN_LABELS.get(plan, 'Free')}")
    st.session_state.plan = plan
    st.caption(signed_in.email)
    if st.button("Log ud", width="stretch"):
        _logout()

if st.session_state.get("main_view") == "account":
    account_page.render_account(signed_in, plan, _logout)
    st.stop()

single_tab, watch_tab = st.tabs(["Enkelt Aktie", "Watchlist Overblik"])

with single_tab:
    plan = st.session_state.plan

    def market_label(country: str) -> str:
        label = access.MARKET_LABELS[country]
        if access.can_access_market(country, plan):
            return label
        return f"{label} 🔒"

    if st.session_state.get("selected_market") not in access.MARKETS:
        st.session_state.selected_market = "denmark"
    st.selectbox("Marked", options=list(access.MARKETS), format_func=market_label, key="selected_market")
    market = st.session_state.selected_market
    market_stocks = access.stocks_in_market(market)
    market_codes = list(market_stocks)
    stock_key = f"selected_symbol__{market}"
    if market_codes and st.session_state.get(stock_key) not in market_codes:
        _market, default_symbol = access.aligned_selection(market, None, plan)
        st.session_state[stock_key] = default_symbol

    def stock_label(code: str) -> str:
        name = market_stocks[code]
        shown = f"{name} ({code})"
        if access.may_analyse(code, plan, market):
            return shown
        return f"{shown} 🔒"

    symbol = st.selectbox("Aktie", options=market_codes, format_func=stock_label, key=stock_key)
    if symbol not in market_codes or access.market_of(symbol) != market:
        _market, symbol = access.aligned_selection(market, None, plan)
    history = pd.DataFrame()
    quote = {}
    fetch_failed = False
    allowed = access.may_analyse(symbol, plan, st.session_state.selected_market)
    if not symbol:
        st.info("Vælg en aktie.")
    elif not allowed:
        required = access.minimum_plan_for_ticker(symbol) or access.minimum_plan_for_market(st.session_state.selected_market)
        if required:
            st.info(f"🔒 {access.upgrade_message(required)}")
        else:
            st.info("Den aktie er ikke en del af TraderDash.")
    else:
        with st.spinner(f"Henter {symbol}..."):
            try:
                history = load_history(symbol, period)
                quote = {} if history.empty or len(history) < MACD_SLOW + MACD_SIGNAL else load_quote(symbol)
            except Exception:
                fetch_failed = True
                st.error("Kursdata er midlertidigt utilgængelige. Prøv igen om et øjeblik.")
                history = pd.DataFrame()
                quote = {}

    if allowed and symbol and not fetch_failed and (history.empty or len(history) < MACD_SLOW + MACD_SIGNAL):
        st.error(
            _fetch_notice(history, quote)
            or f"Fandt ikke nok kursdata for {symbol}. Tjek fondskoden, eller vælg en længere periode."
        )
    elif allowed and symbol and not fetch_failed:
        quote_notice = quote.get("_notice")
        if quote_notice:
            st.warning(str(quote_notice))
        updated = describe_freshness(history)
        if updated:
            st.caption(updated)
        snapshot = signal_snapshot(history, quote, risk_free_rate)
        render_split_cards(snapshot["cards"], fundamental_cards(quote))
        st.plotly_chart(
            build_chart(history, snapshot["rsi"], snapshot["macd"], symbol),
            width="stretch",
        )
        assessment = manager_assessment(market_stocks.get(symbol, symbol), symbol, snapshot)
        if snapshot["stance"] == "LONG":
            st.success(assessment)
        elif snapshot["stance"] == "SHORT":
            st.error(assessment)
        else:
            st.warning(assessment)

with watch_tab:
    st.caption("Grøn række er LONG. Rød række er SHORT. Gul række er neutral.")
    show_watchlist = st.button("Opdater overblik", type="primary")
    if show_watchlist:
        st.session_state.watch_ready = True

    if st.session_state.get("watch_ready"):
        entitled = access.get_allowed_stocks(st.session_state.plan)
        codes = [code for code in entitled if access.may_analyse(code, st.session_state.plan)]
        if not codes:
            st.info("Ingen aktier på denne plan.")
        else:
            rows = []
            notices: list[str] = []
            progress = st.progress(0, text="Henter watchlist...")
            for index, code in enumerate(codes, start=1):
                if not access.may_analyse(code, st.session_state.plan):
                    continue
                progress.progress(index / len(codes), text=f"Henter {code} ({index}/{len(codes)})")
                try:
                    item_history = load_history(code, period)
                    history_ready = not item_history.empty and len(item_history) >= MACD_SLOW + MACD_SIGNAL
                    item_quote = load_quote(code) if history_ready else {}
                except Exception:
                    item_history = pd.DataFrame()
                    item_quote = {}
                    history_ready = False
                    notices.append("Kursdata er midlertidigt utilgængelige. Prøv igen om et øjeblik.")
                notice = _fetch_notice(item_history, item_quote)
                if notice:
                    notices.append(notice)
                if not history_ready:
                    rows.append(
                        {
                            "Aktie": entitled.get(code, code),
                            "Kode": code,
                            "Kurs": "—",
                            "Ændring": "—",
                            "Køb": 0,
                            "Sælg": 0,
                            "Afvent": 0,
                            "Retning": "INGEN DATA",
                            "Køb fra": "",
                            "Salg fra": "",
                            "_net": -999,
                        }
                    )
                    continue
                item = signal_snapshot(item_history, item_quote, risk_free_rate)
                rows.append(
                    {
                        "Aktie": entitled.get(code, code),
                        "Kode": code,
                        "Kurs": f"{item['price']:,.2f}",
                        "Ændring": f"{item['change']:+.1%}",
                        "Køb": len(item["buys"]),
                        "Sælg": len(item["sells"]),
                        "Afvent": len(item["waits"]),
                        "Retning": item["stance"],
                        "Køb fra": ", ".join(item["buys"]),
                        "Salg fra": ", ".join(item["sells"]),
                        "_net": len(item["buys"]) - len(item["sells"]),
                    }
                )
            progress.empty()
            if notices:
                st.warning(list(dict.fromkeys(notices))[0])
            overview = pd.DataFrame(rows).sort_values("_net", ascending=False).drop(columns="_net")
            st.dataframe(overview.style.apply(paint_watch_row, axis=1), width="stretch", hide_index=True)
