"""
smart-lab.ru scraper — Russian IFRS fundamentals.
Provides: P/E, EV/EBITDA, P/BV, P/S, ROE, Net Margin, Revenue, EBITDA,
          Net Income, Net Debt, Dividend Yield, YoY growth rates.
"""

import math
import time
from typing import Optional, Dict, List, Any

import requests
from bs4 import BeautifulSoup

from ..config import SMARTLAB_BASE, SMARTLAB_TICKER, HEADERS, BANKS


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


def _sl_ticker(ticker: str) -> str:
    return SMARTLAB_TICKER.get(ticker, ticker)


def _extract_row(soup: BeautifulSoup, msfo_field: str, sl_ticker: str) -> List[Optional[float]]:
    """Find a row in smart-lab's financial table by the MSFO field name in href."""
    for a in soup.find_all('a', href=True):
        href = a['href']
        if (f'/q/{sl_ticker}/MSFO/{msfo_field}/' in href or
                f'/q/{sl_ticker.upper()}/MSFO/{msfo_field}/' in href):
            row = a.find_parent('tr')
            if row:
                tds = row.find_all('td')
                values = []
                for td in tds:
                    txt = td.get_text(strip=True)
                    if txt:
                        values.append(_safe_float(txt))
                return values
    return []


def _dedup_ltm(vals: List[Optional[float]]) -> List[Optional[float]]:
    """smart-lab duplicates last year as LTM — remove duplicate tail."""
    if len(vals) >= 2 and vals[-1] == vals[-2]:
        return vals[:-1]
    return vals


def _calc_yoy(vals: List[Optional[float]]) -> Optional[float]:
    """Calculate YoY growth from last two non-None values."""
    clean = [v for v in vals if v is not None]
    if len(clean) >= 2:
        curr, prev = clean[-1], clean[-2]
        if prev != 0:
            return (curr / prev - 1) * 100.0
    return None


def fetch_ticker(ticker: str) -> Dict[str, Any]:
    """Scrape smart-lab.ru for fundamental metrics of a single ticker."""
    sl_ticker = _sl_ticker(ticker)
    url = f"{SMARTLAB_BASE}/{sl_ticker}/f/y/"

    result: Dict[str, Any] = {
        "source": "smartlab",
        "ticker": ticker,
        "pe": None, "pbv": None, "ps": None, "ev_ebitda": None,
        "roe": None, "net_margin": None,
        "revenue_b": None, "ebitda_b": None, "net_income_b": None,
        "net_debt_b": None, "nd_ebitda": None,
        "div_yield": None, "mktcap_b": None,
        "rev_yoy": None, "ni_yoy": None, "ebitda_yoy": None,
        "fiscal_year": None,       # e.g. "2025"
        "fiscal_year_prev": None,  # e.g. "2024"
        "notes": [],
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            result["notes"].append(f"HTTP {resp.status_code}")
            return result

        soup = BeautifulSoup(resp.text, 'lxml')

        # Extract fiscal year columns from table header
        for tr in soup.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['th', 'td'])]
            years = [c for c in cells if c.isdigit() and len(c) == 4]
            if len(years) >= 2:
                result["fiscal_year"] = years[-1]      # latest year
                result["fiscal_year_prev"] = years[-2]  # previous year
                break

        def get_vals(field):
            return _extract_row(soup, field, sl_ticker)

        # ── Valuation multiples (LTM = last value) ──
        pe_vals = get_vals("p_e")
        if pe_vals:
            result["pe"] = pe_vals[-1]

        pbv_vals = get_vals("p_bv")
        if pbv_vals:
            result["pbv"] = pbv_vals[-1]

        ps_vals = get_vals("p_s")
        if ps_vals:
            result["ps"] = ps_vals[-1]

        ev_ebitda_vals = get_vals("ev_ebitda")
        if ev_ebitda_vals:
            result["ev_ebitda"] = ev_ebitda_vals[-1]

        # ── Quality ──
        roe_vals = get_vals("roe")
        if roe_vals:
            result["roe"] = roe_vals[-1]

        nm_vals = get_vals("net_margin")
        if nm_vals:
            result["net_margin"] = nm_vals[-1]

        # ── Financials (in ₽B on smart-lab) ──
        rev_vals = get_vals("revenue")
        if rev_vals:
            rv = _dedup_ltm(rev_vals)
            result["revenue_b"] = rv[-1]
            result["rev_yoy"] = _calc_yoy(rv)

        ebitda_vals = get_vals("ebitda")
        if ebitda_vals:
            ev = _dedup_ltm(ebitda_vals)
            result["ebitda_b"] = ev[-1]
            result["ebitda_yoy"] = _calc_yoy(ev)

        ni_vals = get_vals("net_income")
        if ni_vals:
            nv = _dedup_ltm(ni_vals)
            result["net_income_b"] = nv[-1]
            result["ni_yoy"] = _calc_yoy(nv)

        # ── Balance sheet ──
        nd_vals = get_vals("net_debt")
        if nd_vals:
            result["net_debt_b"] = nd_vals[-1]

        nde_vals = get_vals("debt_ebitda")
        if nde_vals:
            result["nd_ebitda"] = nde_vals[-1]

        # ── Market cap ──
        mc_vals = get_vals("market_cap")
        if mc_vals:
            result["mktcap_b"] = mc_vals[-1]

        # ── Dividend yield ──
        dy_vals = get_vals("div_yield")
        if dy_vals:
            result["div_yield"] = dy_vals[-1]

        # ── Bank-specific fallbacks ──
        if ticker in BANKS:
            if not rev_vals:
                noi_vals = get_vals("net_operating_income")
                if noi_vals:
                    rv = _dedup_ltm(noi_vals)
                    result["revenue_b"] = rv[-1]
                    result["rev_yoy"] = _calc_yoy(rv)

            if result["pbv"] is None:
                pb_vals = get_vals("p_b")
                if pb_vals:
                    result["pbv"] = pb_vals[-1]

    except Exception as e:
        result["notes"].append(f"error: {type(e).__name__}")

    return result


def fetch_all(tickers: List[str], delay: float = 0.7) -> Dict[str, Dict]:
    """Fetch smart-lab data for all tickers with polite delays."""
    results = {}
    for i, t in enumerate(tickers):
        if i > 0:
            time.sleep(delay)
        results[t] = fetch_ticker(t)
    return results
