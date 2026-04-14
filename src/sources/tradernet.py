"""
Tradernet (Freedom Finance) — Price cross-check source.
Free API, no auth needed.
Provides: real-time price, previous close, 52-week range, daily change, volume.
"""

import math
from typing import Optional, Dict, List, Any

import requests

from ..config import HEADERS


TRADERNET_URL = "https://tradernet.com/securities/export"

# Tradernet uses same tickers as MOEX for most stocks
TRADERNET_TICKER = {
    "TCSG": "T",
    "VK": "VKCO",
}


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _tn_ticker(ticker: str) -> str:
    return TRADERNET_TICKER.get(ticker, ticker)


def fetch_ticker(ticker: str) -> Dict[str, Any]:
    """Fetch price data from Tradernet for a single ticker."""
    result: Dict[str, Any] = {
        "source": "tradernet",
        "ticker": ticker,
        "price": None,
        "prev_price": None,
        "change_pct": None,
        "high_52w": None,
        "low_52w": None,
        "volume_rub": None,
        "notes": [],
    }

    tn_ticker = _tn_ticker(ticker)

    try:
        resp = requests.get(
            TRADERNET_URL,
            params={"tickers": tn_ticker},
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=8,
        )

        if resp.status_code != 200:
            result["notes"].append(f"HTTP {resp.status_code}")
            return result

        data = resp.json()
        if not isinstance(data, list) or not data:
            result["notes"].append("empty response")
            return result

        item = data[0]

        result["price"] = _safe_float(item.get("ltp"))        # last trade price
        result["prev_price"] = _safe_float(item.get("ClosePrice"))  # previous close
        result["volume_rub"] = _safe_float(item.get("vlt"))    # volume in RUB

        # 52-week range — filter out 0.0 (Tradernet returns 0 when data unavailable)
        h52 = _safe_float(item.get("x_max"))
        l52 = _safe_float(item.get("x_min"))
        result["high_52w"] = h52 if h52 and h52 > 0 else None
        result["low_52w"] = l52 if l52 and l52 > 0 else None

        # Calculate daily change from close
        if result["price"] and result["prev_price"] and result["prev_price"] > 0:
            result["change_pct"] = ((result["price"] - result["prev_price"]) / result["prev_price"]) * 100.0

    except Exception as e:
        result["notes"].append(f"error: {type(e).__name__}")

    return result


def fetch_all(tickers: List[str]) -> Dict[str, Dict]:
    """Fetch Tradernet data for all tickers (individual requests)."""
    results = {}
    for t in tickers:
        results[t] = fetch_ticker(t)
    return results
