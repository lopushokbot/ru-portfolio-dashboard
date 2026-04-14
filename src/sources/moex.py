"""
MOEX ISS API — Official Moscow Exchange data.
Provides: price, market cap, dividends (trailing 12m), volume, daily change.
"""

import json
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

import requests

from ..config import MOEX_BASE, MOEX_TICKER, HEADERS


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            v = v.replace('\xa0', '').replace(' ', '').replace(',', '.').replace('%', '').strip()
            if not v or v in ('—', '-', 'N/A'):
                return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _moex_ticker(ticker: str) -> str:
    return MOEX_TICKER.get(ticker, ticker)


def _moex_get_json(url: str, params: dict = None) -> dict:
    try:
        resp = requests.get(
            url,
            params=params,
            headers={"User-Agent": HEADERS["User-Agent"], "Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        text = resp.content.decode('utf-8-sig')
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_error": "Response is not JSON"}
    except Exception as e:
        return {"_error": str(e)}


def _block_to_dicts(data: dict, block_name: str) -> List[Dict]:
    block = data.get(block_name, {})
    cols = block.get("columns", [])
    rows = block.get("data", [])
    return [dict(zip(cols, row)) for row in rows]


def fetch_market(ticker: str) -> dict:
    """Fetch real-time price and market cap from MOEX TQBR board."""
    mt = _moex_ticker(ticker)
    url = f"{MOEX_BASE}/engines/stock/markets/shares/boards/TQBR/securities/{mt}.json"
    data = _moex_get_json(url, {"iss.meta": "off"})

    if "_error" in data:
        return {"error": data["_error"]}

    sec_rows = _block_to_dicts(data, "securities")
    mkt_rows = _block_to_dicts(data, "marketdata")

    sec = sec_rows[0] if sec_rows else {}
    mkt = mkt_rows[0] if mkt_rows else {}

    price = _safe_float(mkt.get("LAST")) or _safe_float(sec.get("PREVPRICE"))
    prev_price = _safe_float(sec.get("PREVPRICE"))
    shares = _safe_float(sec.get("ISSUESIZE"))

    mktcap = _safe_float(mkt.get("ISSUECAPITALIZATION"))
    if not mktcap and price and shares:
        mktcap = price * shares

    # Daily change
    change_pct = None
    if price and prev_price and prev_price > 0:
        change_pct = ((price - prev_price) / prev_price) * 100.0

    volume_rub = _safe_float(mkt.get("VALTODAY"))  # trading volume in RUB

    return {
        "price": price,
        "prev_price": prev_price,
        "change_pct": change_pct,
        "mktcap": mktcap,
        "shares": shares,
        "volume_rub": volume_rub,
    }


def fetch_dividends(ticker: str, current_price: Optional[float]) -> Optional[float]:
    """Fetch trailing 12-month dividend yield from MOEX registry data."""
    mt = _moex_ticker(ticker)
    url = f"{MOEX_BASE}/securities/{mt}/dividends.json"
    data = _moex_get_json(url, {"iss.meta": "off"})

    if "_error" in data:
        return None

    divs = _block_to_dicts(data, "dividends")
    if not divs:
        return None

    cutoff = datetime.now() - timedelta(days=365)
    total_12m = 0.0

    for d in divs:
        date_str = d.get("registryclosedate", "")
        if not date_str:
            continue
        try:
            div_date = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if div_date >= cutoff:
            val = _safe_float(d.get("value"))
            if val and val > 0:
                total_12m += val

    if total_12m > 0 and current_price and current_price > 0:
        return (total_12m / current_price) * 100.0
    return None


def fetch_ticker(ticker: str) -> Dict[str, Any]:
    """
    Fetch all MOEX data for a single ticker.
    Returns standardized dict with metric names matching config.
    """
    market = fetch_market(ticker)
    if "error" in market:
        return {
            "source": "moex",
            "ticker": ticker,
            "error": market["error"],
            "price": None,
            "change_pct": None,
            "mktcap": None,
            "div_yield": None,
            "volume_rub": None,
        }

    price = market.get("price")
    div_yield = fetch_dividends(ticker, price)

    return {
        "source": "moex",
        "ticker": ticker,
        "price": price,
        "prev_price": market.get("prev_price"),
        "change_pct": market.get("change_pct"),
        "mktcap": market.get("mktcap"),
        "div_yield": div_yield,
        "volume_rub": market.get("volume_rub"),
    }


def fetch_history_52w(ticker: str) -> Dict[str, Optional[float]]:
    """Fetch 52-week high/low from MOEX historical data (independent of Tradernet)."""
    mt = _moex_ticker(ticker)
    # Get ~260 trading days of history
    from datetime import date
    start = (date.today() - timedelta(days=370)).isoformat()
    url = (f"{MOEX_BASE}/history/engines/stock/markets/shares/boards/TQBR"
           f"/securities/{mt}/candles.json")
    data = _moex_get_json(url, {
        "iss.meta": "off",
        "interval": "24",       # daily candles
        "from": start,
        "limit": "500",
    })

    if "_error" in data:
        return {"high_52w": None, "low_52w": None}

    candles = _block_to_dicts(data, "candles")
    if not candles:
        return {"high_52w": None, "low_52w": None}

    highs = [_safe_float(c.get("high")) for c in candles if _safe_float(c.get("high"))]
    lows = [_safe_float(c.get("low")) for c in candles if _safe_float(c.get("low"))]

    return {
        "high_52w": max(highs) if highs else None,
        "low_52w": min(lows) if lows else None,
    }


def fetch_ticker(ticker: str) -> Dict[str, Any]:
    """
    Fetch all MOEX data for a single ticker.
    Returns standardized dict with metric names matching config.
    """
    market = fetch_market(ticker)
    if "error" in market:
        return {
            "source": "moex",
            "ticker": ticker,
            "error": market["error"],
            "price": None,
            "change_pct": None,
            "mktcap": None,
            "div_yield": None,
            "volume_rub": None,
            "high_52w": None,
            "low_52w": None,
        }

    price = market.get("price")
    div_yield = fetch_dividends(ticker, price)
    hist = fetch_history_52w(ticker)

    return {
        "source": "moex",
        "ticker": ticker,
        "price": price,
        "prev_price": market.get("prev_price"),
        "change_pct": market.get("change_pct"),
        "mktcap": market.get("mktcap"),
        "div_yield": div_yield,
        "volume_rub": market.get("volume_rub"),
        "high_52w": hist.get("high_52w"),
        "low_52w": hist.get("low_52w"),
    }


def fetch_all(tickers: List[str]) -> Dict[str, Dict]:
    """Fetch MOEX data for all tickers. Returns {ticker: data_dict}."""
    results = {}
    for t in tickers:
        results[t] = fetch_ticker(t)
    return results
