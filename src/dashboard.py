#!/usr/bin/env python3
"""
Russian Portfolio Dashboard v2 — Main orchestrator.
Fetches data from 5 sources, cross-validates, generates HTML.

Sources (priority order):
  1. T-Bank Invest API — PRIMARY for fundamentals (P/E, P/BV, ROE, revenue, etc.)
  2. MOEX ISS API — official exchange (prices, market cap, dividends, 52w range)
  3. smart-lab.ru — IFRS fundamentals cross-check + balance sheet
  4. Tradernet (Freedom Finance) — price cross-check, 52-week range
  5. dohod.ru — dividend yield cross-check

Usage:
    python -m src.dashboard
    python -m src.dashboard --output /path/to/output.html
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import PORTFOLIO, SECTORS, TICKER_NAMES
from src.sources import moex, smartlab, tradernet, dohod, tbank
from src.engine.validator import validate_all
from src.render.html_builder import build_html

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dashboard")


def _ensure_deps():
    """Auto-install missing dependencies."""
    missing = []
    try:
        import requests
    except ImportError:
        missing.append("requests")
    try:
        import bs4
    except ImportError:
        missing.append("beautifulsoup4")
    try:
        import lxml
    except ImportError:
        missing.append("lxml")
    if missing:
        import subprocess
        log.info(f"Installing missing deps: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q"] + missing)


def _load_tbank_token() -> str:
    """Load T-Bank API token from .env file or environment."""
    # Check environment variable first
    token = os.environ.get("TBANK_TOKEN")
    if token:
        return token

    # Try .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TBANK_TOKEN="):
                    return line.split("=", 1)[1].strip()

    return ""


def _collect_all_tickers() -> List[str]:
    """Gather all unique tickers: portfolio + benchmark peers."""
    seen = set()
    all_tickers = []
    for t in PORTFOLIO:
        if t not in seen:
            all_tickers.append(t)
            seen.add(t)
    for sector in SECTORS:
        for t in sector["tickers"]:
            if t not in seen:
                all_tickers.append(t)
                seen.add(t)
    return all_tickers


def run(output_path: str = None):
    """Main entry point: fetch, validate, render."""
    _ensure_deps()

    generated_at = datetime.now()
    all_tickers = _collect_all_tickers()
    tbank_token = _load_tbank_token()

    log.info(f"Dashboard v2 — {generated_at.strftime('%Y-%m-%d %H:%M')}")
    log.info(f"Tracking {len(PORTFOLIO)} portfolio + {len(all_tickers) - len(PORTFOLIO)} benchmark = {len(all_tickers)} total")
    if tbank_token:
        log.info(f"  T-Bank API: token loaded")
    else:
        log.warning(f"  T-Bank API: no token — fundamentals will use smart-lab only")

    # ── Fetch from all sources in parallel ──
    moex_data = {}
    smartlab_data = {}
    tradernet_data = {}
    dohod_data = {}
    tbank_data = {}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {}

        # T-Bank — PRIMARY fundamentals (API, sequential for rate limits)
        if tbank_token:
            futures[pool.submit(tbank.fetch_all, all_tickers, tbank_token)] = "tbank"

        # MOEX — official prices + dividends + 52w history
        futures[pool.submit(moex.fetch_all, all_tickers)] = "moex"

        # Tradernet — price cross-check
        futures[pool.submit(tradernet.fetch_all, all_tickers)] = "tradernet"

        # smart-lab — fundamentals cross-check (sequential with delays)
        futures[pool.submit(smartlab.fetch_all, all_tickers, 0.7)] = "smartlab"

        # dohod.ru — dividend cross-check (sequential with delays)
        futures[pool.submit(dohod.fetch_all, all_tickers, 0.5)] = "dohod"

        for future in as_completed(futures):
            source_name = futures[future]
            try:
                result = future.result()
                if source_name == "tbank":
                    tbank_data = result
                    ok = sum(1 for v in result.values() if v.get("pe") is not None or v.get("revenue_b") is not None)
                    log.info(f"  ✅ T-Bank: {ok}/{len(result)} with fundamentals")
                elif source_name == "moex":
                    moex_data = result
                    log.info(f"  ✅ MOEX: {len(result)} tickers")
                elif source_name == "smartlab":
                    smartlab_data = result
                    ok = sum(1 for v in result.values() if v.get("pe") is not None or v.get("revenue_b") is not None)
                    log.info(f"  ✅ smart-lab: {ok}/{len(result)} with data")
                elif source_name == "tradernet":
                    tradernet_data = result
                    ok = sum(1 for v in result.values() if v.get("price") is not None)
                    log.info(f"  ✅ Tradernet: {ok}/{len(result)} with data")
                elif source_name == "dohod":
                    dohod_data = result
                    ok = sum(1 for v in result.values() if v.get("div_yield") is not None)
                    log.info(f"  ✅ dohod.ru: {ok}/{len(result)} with dividend data")
            except Exception as e:
                log.warning(f"  ❌ {source_name}: {str(e)[:100]}")

    # ── Cross-validate ──
    log.info("Cross-validating...")
    validated = validate_all(moex_data, smartlab_data, tradernet_data, dohod_data, tbank_data, all_tickers)

    log.info(f"  Verified: {validated['confidence_pct']:.0f}%")
    log.info(f"  Cross-checked: {validated['verified_count']} · Single-source: {validated['single_count']} · Divergent: {validated['divergent_count']}")
    log.info(f"  Audit flags: {len(validated['audit'])}")

    # ── Render HTML ──
    log.info("Rendering HTML...")
    html = build_html(validated, generated_at)

    # ── Write output ──
    if output_path is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "ru_portfolio_dashboard.html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"✅ Dashboard saved: {output_path}")
    log.info(f"   Size: {len(html) / 1024:.0f} KB")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Russian Portfolio Dashboard v2")
    parser.add_argument("--output", "-o", help="Output HTML file path")
    args = parser.parse_args()

    run(output_path=args.output)


if __name__ == "__main__":
    main()
