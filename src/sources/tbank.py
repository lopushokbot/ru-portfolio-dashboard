"""
T-Bank Invest API — PRIMARY fundamentals source.
Provides: P/E, P/BV, P/S, EV/EBITDA, ROE, ROA, Revenue, EBITDA, Net Income,
          EPS, Dividend Yield, Growth Rates, Market Cap, 52w Range, Beta,
          Total Debt, Net Debt/EBITDA, Free Cash Flow, Enterprise Value.
"""

import math
from typing import Optional, Dict, List, Any

import requests

from ..config import HEADERS

TBANK_BASE = "https://invest-public-api.tinkoff.ru/rest"

TBANK_TICKER = {
    "TCSG": "T",
    "VK": "VKCO",
}

# Fields where 0.0 genuinely means "not available" from T-Bank API
# (these are never actually zero for a real public company)
_ZERO_MEANS_MISSING = {
    # Always positive for any company
    "revenueTtm", "marketCapitalization", "sharesOutstanding",
    "highPriceLast52Weeks", "lowPriceLast52Weeks",
    "numberOfEmployees",
    # T-Bank returns 0.0 when metric is not computed (e.g. banks have no EBITDA)
    "ebitdaTtm", "evToEbitdaMrq", "evToSales",
    "netDebtToEbitda", "totalDebtToEbitdaMrq",
    "totalEnterpriseValueMrq",
    # Valuation — 0 P/E means loss-making, but T-Bank uses 0 for "not computed"
    "peRatioTtm", "priceToFreeCashFlowTtm",
    # Quality — 0 margin/ROE means T-Bank hasn't computed it (banks especially)
    "netMarginMrq", "netInterestMarginMrq",
    # Dividends — 0 means no dividend
    "dividendRateTtm", "dividendsPerShare",
    # Growth — T-Bank returns 0 when not computed
    "oneYearAnnualRevenueGrowthRate", "threeYearAnnualRevenueGrowthRate",
    "fiveYearAnnualRevenueGrowthRate",
}


def _safe(v, field: str = "") -> Optional[float]:
    """Convert value to float. For fields in _ZERO_MEANS_MISSING, treat 0.0 as None."""
    if v is None:
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        if f == 0.0 and field in _ZERO_MEANS_MISSING:
            return None
        return f
    except (ValueError, TypeError):
        return None


def _to_billions(v, field: str = "") -> Optional[float]:
    f = _safe(v, field)
    if f is not None:
        return f / 1e9
    return None


def _tbank_ticker(ticker: str) -> str:
    return TBANK_TICKER.get(ticker, ticker)


def _api_call(endpoint: str, body: dict, token: str) -> dict:
    url = f"{TBANK_BASE}/{endpoint}"
    resp = requests.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return {"_error": f"HTTP {resp.status_code}: {resp.text[:100]}"}
    return resp.json()


def _resolve_instrument(ticker: str, token: str) -> Dict[str, Optional[str]]:
    tb_ticker = _tbank_ticker(ticker)
    data = _api_call(
        "tinkoff.public.invest.api.contract.v1.InstrumentsService/ShareBy",
        {"idType": "INSTRUMENT_ID_TYPE_TICKER", "classCode": "TQBR", "id": tb_ticker},
        token,
    )
    if "_error" in data:
        return {"figi": None, "asset_uid": None, "error": data["_error"]}
    instrument = data.get("instrument", {})
    return {
        "figi": instrument.get("figi"),
        "asset_uid": instrument.get("assetUid"),
        "uid": instrument.get("uid"),
    }


def _fetch_fundamentals_batch(asset_uids: List[str], token: str) -> List[dict]:
    """Fetch fundamentals for multiple assets in one API call."""
    data = _api_call(
        "tinkoff.public.invest.api.contract.v1.InstrumentsService/GetAssetFundamentals",
        {"assets": asset_uids},
        token,
    )
    if "_error" in data:
        return []
    return data.get("fundamentals", [])


def _parse_fundamentals(fund: dict) -> Dict[str, Any]:
    """Parse T-Bank fundamentals response into our metric names."""

    def g(field: str):
        """Get field value with proper zero handling."""
        return _safe(fund.get(field), field)

    def gb(field: str):
        """Get field value and convert to billions."""
        return _to_billions(fund.get(field), field)

    result: Dict[str, Any] = {
        "source": "tbank",
        # Valuation
        "pe": g("peRatioTtm"),
        "pbv": g("priceToBookTtm"),
        "ps": g("priceToSalesTtm"),
        "ev_ebitda": g("evToEbitdaMrq"),
        # Quality
        "roe": g("roe"),
        "roa": g("roa"),
        "net_margin": g("netMarginMrq"),
        # Financials (convert to billions)
        "revenue_b": gb("revenueTtm"),
        "ebitda_b": gb("ebitdaTtm"),
        "net_income_b": gb("netIncomeTtm"),
        "fcf_b": gb("freeCashFlowTtm"),
        # Per share
        "eps": g("epsTtm"),
        # Debt
        "total_debt_b": gb("totalDebtMrq"),
        "nd_ebitda": g("netDebtToEbitda"),
        "debt_to_equity": g("totalDebtToEquityMrq"),
        # Enterprise value
        "ev_b": gb("totalEnterpriseValueMrq"),
        # Dividends
        "div_yield": g("dividendYieldDailyTtm"),
        "div_payout_ratio": g("dividendPayoutRatioFy"),
        "div_per_share": g("dividendsPerShare"),
        # Growth
        "rev_yoy": g("oneYearAnnualRevenueGrowthRate"),
        "rev_3y_cagr": g("threeYearAnnualRevenueGrowthRate"),
        # Market
        "mktcap": g("marketCapitalization"),
        "high_52w": g("highPriceLast52Weeks"),
        "low_52w": g("lowPriceLast52Weeks"),
        "beta": g("beta"),
        "free_float": g("freeFloat"),
        "shares_outstanding": g("sharesOutstanding"),
        # Notes
        "notes": [],
    }
    return result


def fetch_all(tickers: List[str], token: str) -> Dict[str, Dict]:
    """
    Fetch T-Bank fundamentals for all tickers.
    Uses batch API for fundamentals, individual calls for instrument resolution.
    """
    results = {}

    # Step 1: Resolve all tickers to asset_uids
    uid_map = {}  # asset_uid -> ticker
    instruments = {}

    for t in tickers:
        inst = _resolve_instrument(t, token)
        instruments[t] = inst
        if inst.get("asset_uid"):
            uid_map[inst["asset_uid"]] = t
        else:
            results[t] = {
                "source": "tbank", "ticker": t,
                "notes": [f"instrument not found: {inst.get('error', 'unknown')}"],
            }

    # Step 2: Batch fetch fundamentals
    if uid_map:
        fund_list = _fetch_fundamentals_batch(list(uid_map.keys()), token)

        for fund in fund_list:
            asset_uid = fund.get("assetUid")
            ticker = uid_map.get(asset_uid)
            if not ticker:
                continue

            parsed = _parse_fundamentals(fund)
            parsed["ticker"] = ticker

            # Step 3: Fetch last price
            inst = instruments.get(ticker, {})
            if inst.get("uid"):
                try:
                    price_data = _api_call(
                        "tinkoff.public.invest.api.contract.v1.MarketDataService/GetLastPrices",
                        {"instrumentId": [inst["uid"]]},
                        token,
                    )
                    if "_error" not in price_data:
                        prices = price_data.get("lastPrices", [])
                        if prices:
                            price_obj = prices[0].get("price", {})
                            units = int(price_obj.get("units", 0))
                            nano = int(price_obj.get("nano", 0))
                            if units > 0 or nano > 0:
                                parsed["price"] = units + nano / 1e9
                except Exception:
                    pass

            results[ticker] = parsed

    # Fill missing tickers with empty results
    for t in tickers:
        if t not in results:
            results[t] = {"source": "tbank", "ticker": t, "notes": ["no data"]}

    return results
