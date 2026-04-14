"""
Cross-validation engine.
Merges data from all sources, computes median values,
detects divergence, assigns confidence badges.
"""

import math
from statistics import median
from typing import Optional, Dict, List, Any, Tuple

from ..config import (
    THRESHOLDS, RATIO_METRICS, PCT_METRICS, ABS_METRICS,
    BANKS, TICKER_NAMES, PORTFOLIO,
)

# Confidence levels
CONFIRMED = "confirmed"    # ✅ all sources agree
CHECK = "check"            # ⚠️ one outlier but median reliable
DIVERGENCE = "divergence"  # 🔴 major disagreement
SINGLE = "single"          # one source only, no cross-check


# ── Metric mapping: which source fields map to our canonical metrics ─────────

# {canonical_metric: {source_name: source_field_name}}
# T-Bank is PRIMARY for fundamentals; others cross-check
METRIC_MAP = {
    # ── Price (MOEX primary, Tradernet + T-Bank cross-check) ──
    "price":        {"moex": "price", "tradernet": "price", "tbank": "price"},
    "change_pct":   {"moex": "change_pct", "tradernet": "change_pct"},
    "prev_price":   {"moex": "prev_price", "tradernet": "prev_price"},
    "volume_rub":   {"moex": "volume_rub", "tradernet": "volume_rub"},

    # ── Valuation (T-Bank primary, smart-lab cross-check) ──
    "pe":           {"tbank": "pe", "smartlab": "pe"},
    "ev_ebitda":    {"tbank": "ev_ebitda", "smartlab": "ev_ebitda"},
    "pbv":          {"tbank": "pbv", "smartlab": "pbv"},
    "ps":           {"tbank": "ps", "smartlab": "ps"},

    # ── Quality (T-Bank primary, smart-lab cross-check) ──
    "roe":          {"tbank": "roe", "smartlab": "roe"},
    "net_margin":   {"tbank": "net_margin", "smartlab": "net_margin"},

    # ── Dividends (T-Bank + MOEX + smart-lab + dohod — 4 sources) ──
    "div_yield":    {"tbank": "div_yield", "moex": "div_yield", "smartlab": "div_yield", "dohod": "div_yield"},

    # ── Financials (T-Bank primary, smart-lab cross-check) ──
    "revenue_b":    {"tbank": "revenue_b", "smartlab": "revenue_b"},
    "ebitda_b":     {"tbank": "ebitda_b", "smartlab": "ebitda_b"},
    "net_income_b": {"tbank": "net_income_b", "smartlab": "net_income_b"},
    "net_debt_b":   {"smartlab": "net_debt_b"},
    "nd_ebitda":    {"tbank": "nd_ebitda", "smartlab": "nd_ebitda"},
    "total_debt_b": {"tbank": "total_debt_b"},
    "debt_to_equity": {"tbank": "debt_to_equity"},

    # ── Growth: T-Bank + smart-lab ──
    "rev_yoy":      {"tbank": "rev_yoy", "smartlab": "rev_yoy"},
    "ebitda_yoy":   {"smartlab": "ebitda_yoy"},
    "ni_yoy":       {"smartlab": "ni_yoy"},

    # ── Market: up to 3 sources ──
    "mktcap":       {"tbank": "mktcap", "moex": "mktcap"},
    "high_52w":     {"tbank": "high_52w", "moex": "high_52w", "tradernet": "high_52w"},
    "low_52w":      {"tbank": "low_52w", "moex": "low_52w", "tradernet": "low_52w"},
    "mktcap_b":     {"smartlab": "mktcap_b"},

    # ── T-Bank enrichment (single-source but valuable) ──
    "beta":         {"tbank": "beta"},
    "eps":          {"tbank": "eps"},
    "fcf_b":        {"tbank": "fcf_b"},
    "ev_b":         {"tbank": "ev_b"},
    "free_float":   {"tbank": "free_float"},
    "div_payout_ratio": {"tbank": "div_payout_ratio"},
    "rev_3y_cagr":  {"tbank": "rev_3y_cagr"},

    # ── dohod.ru enrichment ──
    "div_dsi":      {"dohod": "div_dsi"},
    "div_forecast": {"dohod": "div_forecast_12m"},
}


def _get_threshold_type(metric: str) -> str:
    if metric in RATIO_METRICS:
        return "ratio"
    elif metric in PCT_METRICS:
        return "percentage"
    elif metric in ABS_METRICS:
        return "absolute"
    return "ratio"  # default


def _check_divergence(values: List[float], metric: str) -> Tuple[str, float]:
    """
    Check if values from different sources diverge beyond thresholds.
    Returns (confidence_level, spread_value).
    """
    if len(values) <= 1:
        return (SINGLE if len(values) == 1 else DIVERGENCE), 0.0

    med = median(values)
    threshold_type = _get_threshold_type(metric)

    if threshold_type == "percentage":
        # Absolute spread in percentage points
        spread = max(values) - min(values)
        threshold = THRESHOLDS["percentage"]
        if spread > threshold:
            return DIVERGENCE, spread
        elif spread > threshold * 0.6:
            return CHECK, spread
        return CONFIRMED, spread

    elif threshold_type == "ratio":
        # Relative spread
        if med == 0:
            return CHECK, 0.0
        spread = (max(values) - min(values)) / abs(med)
        threshold = THRESHOLDS["ratio"]
        if spread > threshold:
            return DIVERGENCE, spread * 100
        elif spread > threshold * 0.6:
            return CHECK, spread * 100
        return CONFIRMED, spread * 100

    else:  # absolute
        if med == 0:
            return CHECK, 0.0
        spread = (max(values) - min(values)) / abs(med)
        threshold = THRESHOLDS["absolute"]
        if spread > threshold:
            return DIVERGENCE, spread * 100
        elif spread > threshold * 0.6:
            return CHECK, spread * 100
        return CONFIRMED, spread * 100


def validate_ticker(
    ticker: str,
    moex_data: Dict,
    smartlab_data: Dict,
    tradernet_data: Dict,
    dohod_data: Dict,
    tbank_data: Dict = None,
) -> Dict[str, Any]:
    """
    Cross-validate data from all sources for a single ticker.
    T-Bank is primary for fundamentals; others cross-check.
    """
    all_sources = {
        "tbank": tbank_data or {},
        "moex": moex_data or {},
        "smartlab": smartlab_data or {},
        "tradernet": tradernet_data or {},
        "dohod": dohod_data or {},
    }

    validated = {}
    audit_entries = []

    for metric, source_map in METRIC_MAP.items():
        # Collect values from each source
        source_values = {}
        for src_name, src_field in source_map.items():
            raw = all_sources.get(src_name, {}).get(src_field)
            if raw is not None:
                source_values[src_name] = raw

        if not source_values:
            validated[metric] = {
                "value": None,
                "confidence": SINGLE,
                "sources": {},
                "spread": 0,
            }
            continue

        values_list = list(source_values.values())
        confidence, spread = _check_divergence(values_list, metric)

        # Use median as the display value
        if len(values_list) == 1:
            best_value = values_list[0]
        else:
            best_value = median(values_list)

        validated[metric] = {
            "value": best_value,
            "confidence": confidence,
            "sources": source_values,
            "spread": spread,
        }

        # Generate audit entry for non-confirmed
        if confidence in (CHECK, DIVERGENCE) and len(source_values) > 1:
            audit_entries.append({
                "ticker": ticker,
                "metric": metric,
                "confidence": confidence,
                "spread": spread,
                "values": source_values,
            })

    # ── Sanity checks ──
    sanity_warnings = []

    pe_val = validated.get("pe", {}).get("value")
    if pe_val is not None and pe_val > 200:
        sanity_warnings.append(f"P/E unusually high ({pe_val:.1f}x) — verify")

    roe_val = validated.get("roe", {}).get("value")
    if roe_val is not None and (roe_val > 500 or roe_val < -100):
        sanity_warnings.append(f"ROE extreme ({roe_val:+.1f}%) — possible one-off event")

    rev = validated.get("revenue_b", {}).get("value")
    ebitda = validated.get("ebitda_b", {}).get("value")
    ni = validated.get("net_income_b", {}).get("value")
    if rev is not None and ebitda is not None and ebitda > rev and rev > 0:
        sanity_warnings.append(f"EBITDA (₽{ebitda:.0f}B) > Revenue (₽{rev:.0f}B) — likely data error")
    if rev is not None and ni is not None and ni > rev and rev > 0:
        sanity_warnings.append(f"Net Income (₽{ni:.0f}B) > Revenue (₽{rev:.0f}B) — likely data error")

    nd_ebitda_val = validated.get("nd_ebitda", {}).get("value")
    if nd_ebitda_val is not None and nd_ebitda_val > 5:
        sanity_warnings.append(f"Net Debt/EBITDA = {nd_ebitda_val:.1f}x — high leverage")

    # Collect notes from all sources
    notes = []
    for src_name, src_data in all_sources.items():
        for note in src_data.get("notes", []):
            notes.append(f"[{src_name}] {note}")
    for sw in sanity_warnings:
        notes.append(f"[sanity] {sw}")
        audit_entries.append({
            "ticker": ticker,
            "metric": "sanity",
            "confidence": CHECK,
            "spread": 0,
            "values": {"check": sw},
        })

    return {
        "ticker": ticker,
        "name": TICKER_NAMES.get(ticker, ticker),
        "is_portfolio": ticker in PORTFOLIO,
        "is_bank": ticker in BANKS,
        "metrics": validated,
        "audit": audit_entries,
        "notes": notes,
    }


def validate_all(
    moex_all: Dict[str, Dict],
    smartlab_all: Dict[str, Dict],
    tradernet_all: Dict[str, Dict],
    dohod_all: Dict[str, Dict],
    tbank_all: Dict[str, Dict],
    tickers: List[str],
) -> Dict[str, Any]:
    """
    Cross-validate all tickers.
    T-Bank is primary for fundamentals; others cross-check.
    """
    results = {}
    all_audit = []
    source_health = {
        "tbank": {"ok": 0, "fail": 0},
        "moex": {"ok": 0, "fail": 0},
        "smartlab": {"ok": 0, "fail": 0},
        "tradernet": {"ok": 0, "fail": 0},
        "dohod": {"ok": 0, "fail": 0},
    }

    for t in tickers:
        moex = moex_all.get(t, {})
        smartlab = smartlab_all.get(t, {})
        tradernet = tradernet_all.get(t, {})
        dohod = dohod_all.get(t, {})
        tbank = tbank_all.get(t, {})

        validated = validate_ticker(t, moex, smartlab, tradernet, dohod, tbank)
        results[t] = validated
        all_audit.extend(validated["audit"])

        # Track source health
        if tbank.get("pe") is not None or tbank.get("revenue_b") is not None:
            source_health["tbank"]["ok"] += 1
        else:
            source_health["tbank"]["fail"] += 1

        if moex.get("price") is not None:
            source_health["moex"]["ok"] += 1
        else:
            source_health["moex"]["fail"] += 1

        if smartlab.get("pe") is not None or smartlab.get("revenue_b") is not None:
            source_health["smartlab"]["ok"] += 1
        else:
            source_health["smartlab"]["fail"] += 1

        if tradernet.get("price") is not None:
            source_health["tradernet"]["ok"] += 1
        else:
            source_health["tradernet"]["fail"] += 1

        if dohod.get("div_yield") is not None:
            source_health["dohod"]["ok"] += 1
        else:
            source_health["dohod"]["fail"] += 1

    # Calculate confidence — separate verified (multi-source) from unverified (single)
    total_metrics = 0
    verified_count = 0     # confirmed by 2+ sources
    single_count = 0       # only 1 source, no cross-check
    divergent_count = 0    # sources disagree
    for t_data in results.values():
        for m_name, m_data in t_data["metrics"].items():
            if m_data["value"] is not None:
                total_metrics += 1
                if m_data["confidence"] == CONFIRMED:
                    verified_count += 1
                elif m_data["confidence"] == SINGLE:
                    single_count += 1
                elif m_data["confidence"] in (CHECK, DIVERGENCE):
                    divergent_count += 1

    # Confidence = verified metrics / (verified + divergent), excluding single-source
    multi_source = verified_count + divergent_count
    confidence_pct = (verified_count / multi_source * 100) if multi_source > 0 else 0

    return {
        "stocks": results,
        "audit": all_audit,
        "source_health": source_health,
        "confidence_pct": confidence_pct,
        "total_metrics": total_metrics,
        "verified_count": verified_count,
        "single_count": single_count,
        "divergent_count": divergent_count,
        "_smartlab_raw": smartlab_all,
    }
