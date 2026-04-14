"""
Yahoo Finance — International cross-check for Russian stocks.
Uses yfinance with .ME suffix for MOEX-listed securities.
Provides: P/E, P/B, P/S, ROE, margins, revenue, EBITDA, 52-week range, price.
"""

import math
from typing import Optional, Dict, List, Any

from ..config import YAHOO_TICKER


def _safe(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _to_billions(v) -> Optional[float]:
    f = _safe(v)
    if f is not None:
        return f / 1e9
    return None


def fetch_ticker(ticker: str) -> Dict[str, Any]:
    """
    Fetch Yahoo Finance data for a single Russian stock.
    Returns standardized dict matching our metric names.
    """
    result: Dict[str, Any] = {
        "source": "yahoo",
        "ticker": ticker,
        "price": None, "change_pct": None,
        "pe": None, "pe_forward": None, "pbv": None, "ps": None,
        "roe": None, "net_margin": None,
        "div_yield": None, "mktcap": None,
        "revenue_b": None, "ebitda_b": None, "net_income_b": None,
        "net_debt_b": None,
        "high_52w": None, "low_52w": None,
        "notes": [],
    }

    yahoo_sym = YAHOO_TICKER.get(ticker, f"{ticker}.ME")

    try:
        import yfinance as yf
        t = yf.Ticker(yahoo_sym)
        info = t.info or {}

        if not info or info.get("regularMarketPrice") is None:
            result["notes"].append(f"no data for {yahoo_sym}")
            return result

        # Price
        result["price"] = _safe(info.get("regularMarketPrice"))
        prev = _safe(info.get("regularMarketPreviousClose"))
        if result["price"] and prev and prev > 0:
            result["change_pct"] = ((result["price"] - prev) / prev) * 100.0

        # 52-week range
        result["high_52w"] = _safe(info.get("fiftyTwoWeekHigh"))
        result["low_52w"] = _safe(info.get("fiftyTwoWeekLow"))

        # Valuation
        result["pe"] = _safe(info.get("trailingPE"))
        result["pe_forward"] = _safe(info.get("forwardPE"))
        result["pbv"] = _safe(info.get("priceToBook"))
        result["ps"] = _safe(info.get("priceToSalesTrailing12Months"))

        # Quality
        roe_raw = _safe(info.get("returnOnEquity"))
        if roe_raw is not None:
            result["roe"] = roe_raw * 100.0  # yfinance returns as decimal

        margin_raw = _safe(info.get("profitMargins"))
        if margin_raw is not None:
            result["net_margin"] = margin_raw * 100.0

        # Dividends
        div_raw = _safe(info.get("dividendYield"))
        if div_raw is not None:
            result["div_yield"] = div_raw * 100.0

        # Market cap
        result["mktcap"] = _safe(info.get("marketCap"))

        # Financials (convert to billions RUB)
        result["revenue_b"] = _to_billions(info.get("totalRevenue"))
        result["ebitda_b"] = _to_billions(info.get("ebitda"))
        result["net_income_b"] = _to_billions(info.get("netIncomeToCommon"))

        # Net debt = total debt - total cash
        total_debt = _safe(info.get("totalDebt"))
        total_cash = _safe(info.get("totalCash"))
        if total_debt is not None and total_cash is not None:
            result["net_debt_b"] = (total_debt - total_cash) / 1e9

    except ImportError:
        result["notes"].append("yfinance not installed")
    except Exception as e:
        result["notes"].append(f"error: {str(e)[:80]}")

    return result


def fetch_all(tickers: List[str]) -> Dict[str, Dict]:
    """Fetch Yahoo data for all tickers."""
    results = {}
    for t in tickers:
        results[t] = fetch_ticker(t)
    return results
