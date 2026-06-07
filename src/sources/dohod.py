"""
dohod.ru — Dividend data cross-check.
Scrapes dividend pages for yield, history, and forecasts.
"""

import math
import re
from typing import Optional, Dict, List, Any

import requests
from bs4 import BeautifulSoup

from ..config import HEADERS

DOHOD_BASE = "https://dohod.ru/ik/analytics/dividend"

# dohod.ru uses lowercase MOEX tickers in URL
DOHOD_TICKER = {
    "TCSG": "tcsg",    # dohod.ru still uses the old pre-rebrand ticker; /t returns HTTP 404 (confirmed 2026-06-07)
    "X5": "x5",
    "YDEX": "ydex",
    "LKOH": "lkoh",
    "HEAD": "head",
    "SBER": "sber",
    "NVTK": "nvtk",
    "GMKN": "gmkn",
    "CNRU": "cnru",
    "TATN": "tatn",
    "ROSN": "rosn",
    "GAZP": "gazp",
    "VTBR": "vtbr",
    "BSPB": "bspb",
    "NLMK": "nlmk",
    "MAGN": "magn",
    "CHMF": "chmf",
    "MGNT": "mgnt",
    "OZON": "ozon",
    "VK": "vk",
}


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            v = v.replace('\xa0', '').replace(' ', '').replace(',', '.').replace('%', '').replace('₽', '').strip()
            if not v or v in ('—', '-', 'N/A', 'n/a', '–'):
                return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def fetch_ticker(ticker: str) -> Dict[str, Any]:
    """Scrape dohod.ru dividend page for a single ticker."""
    result: Dict[str, Any] = {
        "source": "dohod",
        "ticker": ticker,
        "div_yield": None,
        "div_dsi": None,          # Dividend Stability Index
        "div_payout_ratio": None,  # Payout ratio (доля прибыли)
        "div_forecast_12m": None,  # Forecast next 12m dividend
        "notes": [],
    }

    dh_ticker = DOHOD_TICKER.get(ticker, ticker.lower())
    url = f"{DOHOD_BASE}/{dh_ticker}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            result["notes"].append(f"HTTP {resp.status_code}")
            return result

        soup = BeautifulSoup(resp.text, 'lxml')

        # The dividend summary is in the first table
        # Structure: row 0 = values [yield, ?, payout_ratio, ?, dsi]
        #            row 1 = labels [текущая доходность, ?, доля от прибыли, ?, индекс DSI]
        tables = soup.find_all('table')

        if tables:
            summary_table = tables[0]
            rows = summary_table.find_all('tr')

            if len(rows) >= 2:
                value_cells = [td.get_text(strip=True) for td in rows[0].find_all('td')]
                label_cells = [td.get_text(strip=True) for td in rows[1].find_all('td')]

                # Parse yield (текущая доходность)
                for i, label in enumerate(label_cells):
                    if 'доходность' in label.lower():
                        val = _safe_float(value_cells[i] if i < len(value_cells) else None)
                        if val is not None:
                            result["div_yield"] = val
                    elif 'dsi' in label.lower():
                        val = _safe_float(value_cells[i] if i < len(value_cells) else None)
                        if val is not None:
                            result["div_dsi"] = val
                    elif 'прибыли' in label.lower():
                        val = _safe_float(value_cells[i] if i < len(value_cells) else None)
                        if val is not None:
                            result["div_payout_ratio"] = val

            # The second table has dividend history
            if len(tables) >= 2:
                div_table = tables[1]
                div_rows = div_table.find_all('tr')
                if len(div_rows) >= 2:
                    forecast_cells = [td.get_text(strip=True) for td in div_rows[1].find_all('td')]
                    if forecast_cells and 'прогноз' in forecast_cells[0].lower():
                        val = _safe_float(forecast_cells[1] if len(forecast_cells) > 1 else None)
                        if val is not None:
                            result["div_forecast_12m"] = val

            # The third table has detailed dates (registry close dates)
            if len(tables) >= 3:
                detail_table = tables[2]
                detail_rows = detail_table.find_all('tr')
                import re
                from datetime import datetime as dt
                today = dt.now()
                for row in detail_rows[1:]:  # skip header
                    cells = [td.get_text(strip=True) for td in row.find_all('td')]
                    if len(cells) >= 4:
                        # cells: [declared_date, registry_date, year, amount]
                        registry_str = cells[1]
                        # Extract date, may have (прогноз)
                        date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', registry_str)
                        if date_match:
                            try:
                                reg_date = dt.strptime(date_match.group(1), "%d.%m.%Y")
                                if reg_date > today:
                                    result["next_div_date"] = reg_date.strftime("%Y-%m-%d")
                                    result["next_div_amount"] = _safe_float(cells[3])
                                    is_forecast = 'прогноз' in registry_str.lower()
                                    result["next_div_forecast"] = is_forecast
                                    break
                            except ValueError:
                                pass

    except Exception as e:
        result["notes"].append(f"error: {type(e).__name__}")

    return result


def fetch_all(tickers: List[str], delay: float = 0.5) -> Dict[str, Dict]:
    """Fetch dohod.ru dividend data for all tickers with polite delays."""
    import time
    results = {}
    for i, t in enumerate(tickers):
        if i > 0:
            time.sleep(delay)
        results[t] = fetch_ticker(t)
    return results
