"""
Finrange.com scraper — Third cross-check source for Russian stocks.
Uses Playwright for JS rendering.
Provides: P/E, Dividend Yield, Market Cap, Revenue, EBITDA.
"""

import math
from typing import Optional, Dict, List, Any

from ..config import FINRANGE_TICKER


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            v = (v.replace('\xa0', '').replace(' ', '').replace(',', '.')
                  .replace('₽', '').replace('%', '').replace('x', '').strip())
            if not v or v in ('—', '-', 'N/A', '–'):
                return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _fr_ticker(ticker: str) -> str:
    return FINRANGE_TICKER.get(ticker, ticker)


def fetch_ticker(ticker: str, playwright_browser=None) -> Dict[str, Any]:
    """
    Scrape Finrange.com for a single ticker using Playwright.
    If playwright_browser is None, attempts to launch one.
    """
    result: Dict[str, Any] = {
        "source": "finrange",
        "ticker": ticker,
        "pe": None, "div_yield": None, "mktcap": None,
        "revenue_b": None, "ebitda_b": None,
        "notes": [],
    }

    fr_ticker = _fr_ticker(ticker)
    url = f"https://finrange.com/company/MOEX-{fr_ticker}"

    try:
        from playwright.sync_api import sync_playwright

        own_browser = playwright_browser is None

        if own_browser:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=True)
        else:
            browser = playwright_browser
            pw = None

        try:
            page = browser.new_page()
            page.set_default_timeout(15000)
            page.goto(url, wait_until="networkidle")

            # Wait for content to render
            page.wait_for_timeout(2000)

            content = page.content()

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'lxml')

            # Extract metrics from the page
            # Finrange displays key metrics in summary cards/tables
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.split('\n') if line.strip()]

            # Look for P/E
            for i, line in enumerate(lines):
                if line in ('P/E', 'P / E') and i + 1 < len(lines):
                    val = _safe_float(lines[i + 1])
                    if val and 0 < val < 500:
                        result["pe"] = val
                        break

            # Look for dividend yield
            for i, line in enumerate(lines):
                low = line.lower()
                if 'дивиденд' in low or 'dividend' in low:
                    # Check nearby lines for a percentage
                    for j in range(i, min(i + 3, len(lines))):
                        if '%' in lines[j]:
                            val = _safe_float(lines[j])
                            if val and 0 < val < 50:
                                result["div_yield"] = val
                                break
                    break

            # Look for market cap
            for i, line in enumerate(lines):
                low = line.lower()
                if ('капитализация' in low or 'market cap' in low) and i + 1 < len(lines):
                    val_str = lines[i + 1]
                    val = _safe_float(val_str)
                    if val:
                        # Determine scale (млрд = billions, трлн = trillions)
                        if i + 2 < len(lines):
                            unit = lines[i + 2].lower()
                            if 'трлн' in unit or 'trl' in unit:
                                val *= 1000  # to billions
                        result["mktcap"] = val * 1e9  # to raw RUB
                    break

            page.close()

        finally:
            if own_browser:
                browser.close()
                if pw:
                    pw.stop()

    except ImportError:
        result["notes"].append("playwright not installed")
    except Exception as e:
        result["notes"].append(f"error: {str(e)[:80]}")

    return result


def fetch_all(tickers: List[str]) -> Dict[str, Dict]:
    """
    Fetch Finrange data for all tickers.
    Opens a single browser instance and reuses it for all tickers.
    """
    results = {}

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for t in tickers:
                    results[t] = fetch_ticker(t, playwright_browser=browser)
            finally:
                browser.close()

    except ImportError:
        # Playwright not available — return empty results
        for t in tickers:
            results[t] = {
                "source": "finrange",
                "ticker": t,
                "pe": None, "div_yield": None, "mktcap": None,
                "revenue_b": None, "ebitda_b": None,
                "notes": ["playwright not installed — skipping Finrange"],
            }
    except Exception as e:
        for t in tickers:
            results[t] = {
                "source": "finrange",
                "ticker": t,
                "pe": None, "div_yield": None, "mktcap": None,
                "revenue_b": None, "ebitda_b": None,
                "notes": [f"browser error: {str(e)[:60]}"],
            }

    return results
