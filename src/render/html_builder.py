"""
HTML renderer for Russian Portfolio Dashboard v2.
Generates a single self-contained HTML file.
"""

import math
from datetime import datetime
from typing import Optional, Dict, List, Any

from ..config import PORTFOLIO, SECTORS, BANKS, TICKER_NAMES


# ── Formatting helpers ───────────────────────────────────────────────────────

def _fmt_price(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if v >= 10000:
        return f"₽{v:,.0f}"
    elif v >= 100:
        return f"₽{v:,.1f}"
    else:
        return f"₽{v:,.2f}"


def _fmt_change(v: Optional[float]) -> str:
    if v is None:
        return ""
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def _fmt_ratio(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if v < 0:
        return "neg"
    return f"{v:.1f}x"


def _fmt_pct(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.1f}%"


def _fmt_pct_unsigned(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:.1f}%"


def _fmt_rub_b(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1000:
        return f"₽{v / 1000:.2f}T"
    elif abs(v) >= 100:
        return f"₽{v:.0f}B"
    elif abs(v) >= 10:
        return f"₽{v:.1f}B"
    else:
        return f"₽{v:.2f}B"


def _fmt_rub(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e12:
        return f"₽{v / 1e12:.2f}T"
    elif abs(v) >= 1e9:
        return f"₽{v / 1e9:.1f}B"
    elif abs(v) >= 1e6:
        return f"₽{v / 1e6:.0f}M"
    else:
        return f"₽{v:,.0f}"


def _confidence_badge(confidence: str) -> str:
    if confidence == "confirmed":
        return '<span class="badge" title="All sources agree">✅</span>'
    elif confidence == "check":
        return '<span class="badge" title="Minor divergence between sources">⚠️</span>'
    elif confidence == "divergence":
        return '<span class="badge" title="Major divergence — check audit tab">🔴</span>'
    else:
        return ''


def _change_class(v: Optional[float]) -> str:
    if v is None:
        return ""
    return "val-green" if v >= 0 else "val-red"


def _tooltip(sources: Dict[str, float], fmt_fn) -> str:
    if not sources:
        return ""
    parts = []
    source_labels = {"tbank": "T-Bank", "moex": "MOEX", "smartlab": "smart-lab", "tradernet": "Tradernet", "dohod": "dohod.ru"}
    for src, val in sources.items():
        label = source_labels.get(src, src)
        parts.append(f"{label}: {fmt_fn(val)}")
    return " | ".join(parts)


def _metric(stock: Dict, name: str) -> Dict:
    return stock.get("metrics", {}).get(name, {"value": None, "confidence": "single", "sources": {}})


def _val(stock: Dict, name: str) -> Optional[float]:
    return _metric(stock, name).get("value")


def _cell(metric_data: Dict, fmt_fn) -> str:
    """Build a table cell with value + confidence badge + tooltip."""
    v = metric_data["value"]
    tip = _tooltip(metric_data.get("sources", {}), fmt_fn)
    badge = _confidence_badge(metric_data["confidence"])
    return f'<td class="num" title="{tip}">{fmt_fn(v)}{badge}</td>'


def _cell_colored(metric_data: Dict, fmt_fn) -> str:
    """Build a cell with green/red coloring + badge."""
    v = metric_data["value"]
    tip = _tooltip(metric_data.get("sources", {}), fmt_fn)
    badge = _confidence_badge(metric_data["confidence"])
    cls = _change_class(v)
    return f'<td class="num {cls}" title="{tip}">{fmt_fn(v)}{badge}</td>'


# ── Table builders ───────────────────────────────────────────────────────────

def _build_valuation_table(stocks: Dict, tickers: List[str], show_portfolio_badge: bool = False) -> str:
    """Valuation table for NON-BANK stocks: P/E, EV/EBITDA, P/S."""
    rows = []
    for t in tickers:
        s = stocks.get(t)
        if not s or s.get("is_bank"):
            continue

        is_p = s.get("is_portfolio", False)
        name = s.get("name", t)
        row_class = "portfolio-row" if is_p and show_portfolio_badge else ""
        dot = ' <span class="portfolio-dot">●</span>' if is_p and show_portfolio_badge else ""

        rows.append(f'''<tr class="{row_class}">
  <td class="ticker">{t}{dot}<span class="name-sub">{name}</span></td>
  <td class="num price">{_fmt_price(_metric(s,"price")["value"])}</td>
  <td class="num {_change_class(_metric(s,"change_pct")["value"])}">{_fmt_change(_metric(s,"change_pct")["value"])}</td>
  {_cell(_metric(s,"pe"), _fmt_ratio)}
  {_cell(_metric(s,"ev_ebitda"), _fmt_ratio)}
  {_cell(_metric(s,"ps"), _fmt_ratio)}
  {_cell(_metric(s,"mktcap"), _fmt_rub)}
</tr>''')

    return '\n'.join(rows)


def _build_bank_table(stocks: Dict, tickers: List[str], show_portfolio_badge: bool = False) -> str:
    """Valuation table for BANK stocks: P/E, P/BV, ROE, Div Yield."""
    rows = []
    for t in tickers:
        s = stocks.get(t)
        if not s or not s.get("is_bank"):
            continue

        is_p = s.get("is_portfolio", False)
        name = s.get("name", t)
        row_class = "portfolio-row" if is_p and show_portfolio_badge else ""
        dot = ' <span class="portfolio-dot">●</span>' if is_p and show_portfolio_badge else ""

        rows.append(f'''<tr class="{row_class}">
  <td class="ticker">{t}{dot}<span class="name-sub">{name}</span></td>
  <td class="num price">{_fmt_price(_metric(s,"price")["value"])}</td>
  <td class="num {_change_class(_metric(s,"change_pct")["value"])}">{_fmt_change(_metric(s,"change_pct")["value"])}</td>
  {_cell(_metric(s,"pe"), _fmt_ratio)}
  {_cell(_metric(s,"pbv"), _fmt_ratio)}
  {_cell(_metric(s,"roe"), _fmt_pct)}
  {_cell(_metric(s,"div_yield"), _fmt_pct_unsigned)}
  {_cell(_metric(s,"mktcap"), _fmt_rub)}
</tr>''')

    return '\n'.join(rows)


def _build_quality_table(stocks: Dict, tickers: List[str], show_portfolio_badge: bool = False) -> str:
    """Quality table for NON-BANK stocks."""
    rows = []
    for t in tickers:
        s = stocks.get(t)
        if not s or s.get("is_bank"):
            continue

        is_p = s.get("is_portfolio", False)
        name = s.get("name", t)
        row_class = "portfolio-row" if is_p and show_portfolio_badge else ""
        dot = ' <span class="portfolio-dot">●</span>' if is_p and show_portfolio_badge else ""

        rows.append(f'''<tr class="{row_class}">
  <td class="ticker">{t}{dot}<span class="name-sub">{name}</span></td>
  <td class="num price">{_fmt_price(_metric(s,"price")["value"])}</td>
  {_cell(_metric(s,"net_margin"), _fmt_pct)}
  {_cell(_metric(s,"roe"), _fmt_pct)}
  {_cell(_metric(s,"div_yield"), _fmt_pct_unsigned)}
</tr>''')

    return '\n'.join(rows)


def _build_growth_table(stocks: Dict, tickers: List[str], show_portfolio_badge: bool = False) -> str:
    """Growth table — all stocks (banks + non-banks)."""
    rows = []
    for t in tickers:
        s = stocks.get(t)
        if not s:
            continue

        is_p = s.get("is_portfolio", False)
        name = s.get("name", t)
        row_class = "portfolio-row" if is_p and show_portfolio_badge else ""
        dot = ' <span class="portfolio-dot">●</span>' if is_p and show_portfolio_badge else ""

        rows.append(f'''<tr class="{row_class}">
  <td class="ticker">{t}{dot}<span class="name-sub">{name}</span></td>
  <td class="num price">{_fmt_price(_metric(s,"price")["value"])}</td>
  {_cell_colored(_metric(s,"rev_yoy"), _fmt_pct)}
  {_cell_colored(_metric(s,"ebitda_yoy"), _fmt_pct)}
  {_cell_colored(_metric(s,"ni_yoy"), _fmt_pct)}
</tr>''')

    return '\n'.join(rows)


def _build_financials_table(stocks: Dict, tickers: List[str], show_portfolio_badge: bool = False) -> str:
    """Financials table — all stocks."""
    rows = []
    for t in tickers:
        s = stocks.get(t)
        if not s:
            continue

        is_p = s.get("is_portfolio", False)
        name = s.get("name", t)
        row_class = "portfolio-row" if is_p and show_portfolio_badge else ""
        dot = ' <span class="portfolio-dot">●</span>' if is_p and show_portfolio_badge else ""

        rows.append(f'''<tr class="{row_class}">
  <td class="ticker">{t}{dot}<span class="name-sub">{name}</span></td>
  <td class="num price">{_fmt_price(_metric(s,"price")["value"])}</td>
  {_cell(_metric(s,"revenue_b"), _fmt_rub_b)}
  {_cell(_metric(s,"ebitda_b"), _fmt_rub_b)}
  {_cell(_metric(s,"net_income_b"), _fmt_rub_b)}
  {_cell(_metric(s,"net_debt_b"), _fmt_rub_b)}
  <td class="num">{_fmt_ratio(_metric(s,"nd_ebitda")["value"])}</td>
</tr>''')

    return '\n'.join(rows)


# ── Sector medians ───────────────────────────────────────────────────────────

def _compute_sector_medians(stocks: Dict, tickers: List[str], metrics: List[str]) -> Dict[str, Optional[float]]:
    """Compute median values for a list of metrics across sector tickers."""
    from statistics import median as stat_median
    result = {}
    for m in metrics:
        vals = []
        for t in tickers:
            s = stocks.get(t)
            if s:
                v = _val(s, m)
                if v is not None:
                    vals.append(v)
        result[m] = stat_median(vals) if vals else None
    return result


def _median_row(medians: Dict[str, Optional[float]], cols: List[tuple]) -> str:
    """Build a 'Sector Median' summary row from computed medians."""
    cells = ['<td class="ticker median-label">Median</td>']
    for metric, fmt_fn in cols:
        v = medians.get(metric)
        cells.append(f'<td class="num median-val">{fmt_fn(v)}</td>')
    return f'<tr class="median-row">{"".join(cells)}</tr>'


# ── Dividend calendar ────────────────────────────────────────────────────────

def _build_dividend_calendar(stocks: Dict, tickers: List[str]) -> str:
    """Build upcoming dividend table from T-Bank and dohod.ru data."""
    rows = []
    for t in tickers:
        s = stocks.get(t)
        if not s:
            continue

        name = s.get("name", t)
        div_date_m = _metric(s, "next_div_date")
        div_amt_m = _metric(s, "next_div_amount")
        div_yield_m = _metric(s, "div_yield")

        div_date = div_date_m.get("value")
        div_amt = div_amt_m.get("value")
        div_yield_val = div_yield_m.get("value")

        if not div_date and not div_amt:
            continue

        date_str = str(div_date) if div_date else "TBD"
        amt_str = f"₽{div_amt:,.1f}" if isinstance(div_amt, (int, float)) else "TBD"
        yield_str = f"{div_yield_val:.1f}%" if div_yield_val else ""

        rows.append(f'''<tr>
  <td class="ticker">{t}<span class="name-sub">{name}</span></td>
  <td class="num">{date_str}</td>
  <td class="num">{amt_str}</td>
  <td class="num">{yield_str}</td>
</tr>''')

    if not rows:
        return '<tr><td colspan="4" class="empty-msg">No upcoming dividends found</td></tr>'
    return '\n'.join(rows)


# ── Sector conclusions ───────────────────────────────────────────────────────

def _build_sector_conclusions(stocks: Dict) -> Dict[str, str]:
    """Generate data-driven sector conclusions using live portfolio data."""
    conclusions = {}

    # ── Oil & Gas ──
    oil_tickers = ["LKOH", "ROSN", "NVTK", "TATN", "GAZP"]
    oil_pes = [_val(stocks.get(t,{}), "pe") for t in oil_tickers if _val(stocks.get(t,{}), "pe") and _val(stocks.get(t,{}), "pe") > 0]
    oil_divs = [_val(stocks.get(t,{}), "div_yield") for t in oil_tickers if _val(stocks.get(t,{}), "div_yield")]
    oil_med_pe = f"{sorted(oil_pes)[len(oil_pes)//2]:.1f}x" if oil_pes else "N/A"
    oil_med_div = f"{sorted(oil_divs)[len(oil_divs)//2]:.1f}%" if oil_divs else "N/A"
    conclusions["🛢️ Oil & Gas"] = (
        f"<strong>Key driver:</strong> Brent near $99 supports earnings, but OPEC+ quota discipline and ruble strength "
        f"(USD/RUB ~76) compress ruble-denominated revenue. Sector trades at median P/E {oil_med_pe} with {oil_med_div} median dividend yield. "
        f"<strong>Risk:</strong> Further oil price decline below $90 or ruble appreciation would squeeze margins. "
        f"<strong>Insight:</strong> TATN and ROSN offer the most defensive positioning with lower breakeven costs; GAZP remains the cheapest by P/E but carries execution risk on gas exports."
    )

    # ── Banks / Fintech ──
    bank_tickers = ["SBER", "TCSG", "VTBR", "BSPB"]
    bank_pes = [_val(stocks.get(t,{}), "pe") for t in bank_tickers if _val(stocks.get(t,{}), "pe") and _val(stocks.get(t,{}), "pe") > 0]
    bank_roes = [_val(stocks.get(t,{}), "roe") for t in bank_tickers if _val(stocks.get(t,{}), "roe")]
    bank_med_pe = f"{sorted(bank_pes)[len(bank_pes)//2]:.1f}x" if bank_pes else "N/A"
    bank_med_roe = f"{sorted(bank_roes)[len(bank_roes)//2]:.1f}%" if bank_roes else "N/A"
    conclusions["🏦 Banks / Fintech"] = (
        f"<strong>Key driver:</strong> CBR key rate at 15% — net interest margins remain elevated, driving strong profitability (median ROE {bank_med_roe}). "
        f"Sector trades at median P/E {bank_med_pe}, historically cheap. Rate cuts expected in H2 2026 would boost loan growth but compress margins. "
        f"<strong>Risk:</strong> Credit quality deterioration if rates stay high too long; regulatory pressure on fees. "
        f"<strong>Insight:</strong> SBER is the quality play (highest market cap, stable dividends); VTBR offers deep value but with higher risk."
    )

    # ── Metals & Mining ──
    met_tickers = ["GMKN", "NLMK", "MAGN", "CHMF"]
    met_divs = [_val(stocks.get(t,{}), "div_yield") for t in met_tickers if _val(stocks.get(t,{}), "div_yield")]
    met_med_div = f"{sorted(met_divs)[len(met_divs)//2]:.1f}%" if met_divs else "N/A"
    conclusions["⛏️ Metals & Mining"] = (
        f"<strong>Key driver:</strong> China demand recovery remains the swing factor for nickel (GMKN) and steel (NLMK, MAGN, CHMF). "
        f"Median dividend yield at {met_med_div} — some companies have suspended or cut dividends, creating wide dispersion. "
        f"<strong>Risk:</strong> Global recession would hit commodity prices; sanctions on Russian metals exports remain a headwind. "
        f"<strong>Insight:</strong> CHMF historically the most shareholder-friendly; GMKN's dividend policy is uncertain — watch board announcements."
    )

    # ── Retail ──
    ret_tickers = ["X5", "MGNT", "OZON"]
    ret_revs = [_val(stocks.get(t,{}), "rev_yoy") for t in ret_tickers if _val(stocks.get(t,{}), "rev_yoy")]
    ret_med_growth = f"{sorted(ret_revs)[len(ret_revs)//2]:+.1f}%" if ret_revs else "N/A"
    conclusions["🛒 Retail"] = (
        f"<strong>Key driver:</strong> Consumer spending resilient despite high rates — median revenue growth {ret_med_growth}. "
        f"X5 dominates offline grocery with the largest store network; OZON is the e-commerce leader scaling towards profitability. "
        f"<strong>Risk:</strong> Inflation squeeze on consumer spending power; wage growth deceleration. "
        f"<strong>Insight:</strong> X5 offers the highest dividend yield in the sector after its special payout; OZON is a growth bet — watch the path to sustainable positive net income."
    )

    # ── Tech / Internet ──
    tech_tickers = ["YDEX", "HEAD", "CNRU", "VK"]
    tech_pes = [_val(stocks.get(t,{}), "pe") for t in tech_tickers if _val(stocks.get(t,{}), "pe") and _val(stocks.get(t,{}), "pe") > 0]
    tech_med_pe = f"{sorted(tech_pes)[len(tech_pes)//2]:.1f}x" if tech_pes else "N/A"
    conclusions["💻 Tech / Internet"] = (
        f"<strong>Key driver:</strong> Digital advertising and HR tech demand strong — sector median P/E at {tech_med_pe}, premium to market justified by growth. "
        f"Yandex dominates search/ride-hailing/cloud; HeadHunter is a near-monopoly in online recruitment with exceptional margins. "
        f"<strong>Risk:</strong> Regulatory pressure on data/AI; VK continues to burn cash with no clear path to profitability. "
        f"<strong>Insight:</strong> HEAD offers the best quality (high ROE, net margins >40%, net cash); CNRU is a niche play on Russian real estate digitalization."
    )

    return conclusions


# ── Full page assembly ───────────────────────────────────────────────────────

def build_html(validated_data: Dict[str, Any], generated_at: datetime) -> str:
    stocks = validated_data["stocks"]
    audit = validated_data["audit"]
    source_health = validated_data["source_health"]
    confidence_pct = validated_data["confidence_pct"]
    verified_count = validated_data.get("verified_count", 0)
    single_count = validated_data.get("single_count", 0)
    divergent_count = validated_data.get("divergent_count", 0)

    date_str = generated_at.strftime("%B %d, %Y")
    time_str = generated_at.strftime("%H:%M MSK")

    # ── Determine fiscal year from smartlab data ──
    fy_current = None
    fy_prev = None
    for t in PORTFOLIO:
        s = validated_data.get("_smartlab_raw", {}).get(t, {})
        if s.get("fiscal_year"):
            fy_current = s["fiscal_year"]
            fy_prev = s.get("fiscal_year_prev")
            break
    fy_label = f"FY{fy_current} vs FY{fy_prev}" if fy_current and fy_prev else "YoY"
    fy_fin_label = f"FY{fy_current}" if fy_current else "Latest"

    # ── Source health indicators ──
    def _src_badge(name, data):
        total = data["ok"] + data["fail"]
        if total == 0:
            return f'<span class="src-badge src-gray">{name} —</span>'
        pct = data["ok"] / total * 100
        cls = "src-green" if pct >= 80 else ("src-amber" if pct >= 50 else "src-red")
        return f'<span class="src-badge {cls}">{name} {data["ok"]}/{total}</span>'

    source_badges = " ".join([
        _src_badge("T-Bank", source_health.get("tbank", {"ok": 0, "fail": 0})),
        _src_badge("MOEX", source_health["moex"]),
        _src_badge("smart-lab", source_health["smartlab"]),
        _src_badge("Tradernet", source_health["tradernet"]),
        _src_badge("dohod.ru", source_health["dohod"]),
    ])

    # ── Split portfolio into banks and non-banks ──
    portfolio_banks = [t for t in PORTFOLIO if t in BANKS]
    portfolio_nonbanks = [t for t in PORTFOLIO if t not in BANKS]

    # ── Portfolio tab tables ──
    portfolio_valuation = _build_valuation_table(stocks, portfolio_nonbanks)
    portfolio_banks_html = _build_bank_table(stocks, portfolio_banks)
    portfolio_quality = _build_quality_table(stocks, portfolio_nonbanks)
    portfolio_growth = _build_growth_table(stocks, PORTFOLIO)
    portfolio_financials = _build_financials_table(stocks, PORTFOLIO)

    # ── Dividend calendar ──
    dividend_calendar_html = _build_dividend_calendar(stocks, PORTFOLIO)

    # ── Sector conclusions ──
    sector_conclusions = _build_sector_conclusions(stocks)

    # ── Sectors tab content ──
    sector_sections = []
    for sector in SECTORS:
        sect_name = sector["name"]
        sect_tickers = sector["tickers"]
        is_bank_sector = sector["is_bank"]

        conclusion = sector_conclusions.get(sect_name, "")
        conclusion_html = f'<div class="sector-conclusion">{conclusion}</div>' if conclusion else ""

        if is_bank_sector:
            bank_rows = _build_bank_table(stocks, sect_tickers, show_portfolio_badge=True)
            medians = _compute_sector_medians(stocks, sect_tickers, ["pe", "pbv", "roe", "div_yield"])
            median_html = _median_row(medians, [
                ("pe", _fmt_ratio), ("pe", lambda _: ""), ("pe", lambda _: ""),  # skip Price, Chg
                ("pe", _fmt_ratio), ("pbv", _fmt_ratio), ("roe", _fmt_pct), ("div_yield", _fmt_pct_unsigned), ("pe", lambda _: ""),
            ])
            # Simpler approach — just build the median row manually for banks
            med_pe = _fmt_ratio(medians.get("pe"))
            med_pbv = _fmt_ratio(medians.get("pbv"))
            med_roe = _fmt_pct(medians.get("roe"))
            med_dy = _fmt_pct_unsigned(medians.get("div_yield"))
            median_row = f'<tr class="median-row"><td class="ticker median-label">Median</td><td></td><td></td><td class="num median-val">{med_pe}</td><td class="num median-val">{med_pbv}</td><td class="num median-val">{med_roe}</td><td class="num median-val">{med_dy}</td><td></td></tr>'

            sector_sections.append(f'''
<div class="section">
  <div class="section-header" onclick="toggleSection(this)">
    <span class="section-title">{sect_name}</span>
    <span class="section-toggle">▼</span>
  </div>
  <div class="section-body">
    {conclusion_html}
    <div class="table-wrap">
      <table class="data-table sortable">
        <thead><tr>
          <th>Ticker</th><th>Price</th><th>Chg</th><th>P/E</th><th>P/BV</th><th>ROE</th><th>Div Yield</th><th>Mkt Cap</th>
        </tr></thead>
        <tbody>{bank_rows}{median_row}</tbody>
      </table>
    </div>
  </div>
</div>''')
        else:
            val_rows = _build_valuation_table(stocks, sect_tickers, show_portfolio_badge=True)
            qual_rows = _build_quality_table(stocks, sect_tickers, show_portfolio_badge=True)

            med_val = _compute_sector_medians(stocks, sect_tickers, ["pe", "ev_ebitda", "ps"])
            med_pe_v = _fmt_ratio(med_val.get("pe"))
            med_ev_v = _fmt_ratio(med_val.get("ev_ebitda"))
            med_ps_v = _fmt_ratio(med_val.get("ps"))
            median_row_val = f'<tr class="median-row"><td class="ticker median-label">Median</td><td></td><td></td><td class="num median-val">{med_pe_v}</td><td class="num median-val">{med_ev_v}</td><td class="num median-val">{med_ps_v}</td><td></td></tr>'

            med_qual = _compute_sector_medians(stocks, sect_tickers, ["net_margin", "roe", "div_yield"])
            med_nm = _fmt_pct(med_qual.get("net_margin"))
            med_roe_q = _fmt_pct(med_qual.get("roe"))
            med_dy_q = _fmt_pct_unsigned(med_qual.get("div_yield"))
            median_row_qual = f'<tr class="median-row"><td class="ticker median-label">Median</td><td></td><td class="num median-val">{med_nm}</td><td class="num median-val">{med_roe_q}</td><td class="num median-val">{med_dy_q}</td></tr>'

            sector_sections.append(f'''
<div class="section">
  <div class="section-header" onclick="toggleSection(this)">
    <span class="section-title">{sect_name}</span>
    <span class="section-toggle">▼</span>
  </div>
  <div class="section-body">
    {conclusion_html}
    <div class="table-wrap">
      <table class="data-table sortable">
        <thead><tr>
          <th>Ticker</th><th>Price</th><th>Chg</th><th>P/E</th><th>EV/EBITDA</th><th>P/S</th><th>Mkt Cap</th>
        </tr></thead>
        <tbody>{val_rows}{median_row_val}</tbody>
      </table>
    </div>
    <div class="table-wrap" style="margin-top:12px">
      <table class="data-table sortable">
        <thead><tr>
          <th>Ticker</th><th>Price</th><th>Net Margin</th><th>ROE</th><th>Div Yield</th>
        </tr></thead>
        <tbody>{qual_rows}{median_row_qual}</tbody>
      </table>
    </div>
  </div>
</div>''')

    sectors_html = '\n'.join(sector_sections)

    # ── Audit tab content ──
    audit_rows = []
    for a in sorted(audit, key=lambda x: (0 if x["confidence"] == "divergence" else 1, x["ticker"])):
        icon = "🔴" if a["confidence"] == "divergence" else "⚠️"
        vals_parts = []
        source_labels = {"tbank": "T-Bank", "moex": "MOEX", "smartlab": "smart-lab", "tradernet": "Tradernet", "dohod": "dohod.ru"}
        for src, val in a["values"].items():
            label = source_labels.get(src, src)
            if isinstance(val, (int, float)):
                vals_parts.append(f"{label}: {val:.2f}")
            else:
                vals_parts.append(f"{label}: {val}")
        vals_str = " | ".join(vals_parts)

        audit_rows.append(f'''<tr>
  <td>{icon}</td>
  <td class="ticker">{a["ticker"]}</td>
  <td>{a["metric"]}</td>
  <td>{a["spread"]:.1f}{'pp' if a["metric"] in ('net_margin', 'roe', 'div_yield', 'change_pct') else '%'}</td>
  <td class="source-vals">{vals_str}</td>
</tr>''')

    audit_html = '\n'.join(audit_rows) if audit_rows else '<tr><td colspan="5" class="empty-msg">No divergences detected — all metrics within thresholds</td></tr>'

    # ── Sources tab content ──
    all_notes = []
    for t in PORTFOLIO:
        s = stocks.get(t)
        if s:
            for note in s.get("notes", []):
                all_notes.append(f"<li><strong>{t}</strong>: {note}</li>")

    notes_html = '\n'.join(all_notes) if all_notes else '<li>No issues detected</li>'

    # ── Assemble full HTML ──
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Russian Portfolio — {date_str}</title>
<meta name="description" content="Russian stock portfolio dashboard with multi-source cross-validation">
<meta property="og:title" content="Russian Portfolio Dashboard — {date_str}">
<meta property="og:description" content="10 Russian stocks tracked across 4 data sources with cross-validation">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #ffffff; --bg-secondary: #f5f5f7; --bg-card: #ffffff;
  --text-primary: #1d1d1f; --text-secondary: #6e6e73; --text-tertiary: #86868b;
  --border: #d2d2d7; --border-light: #e8e8ed;
  --green: #34c759; --green-bg: #e8f9ed; --green-text: #1a7a2e;
  --red: #ff3b30; --red-bg: #ffeae9; --red-text: #c0291f;
  --amber: #ff9500; --amber-bg: #fff4e0; --amber-text: #996300;
  --blue: #007aff; --blue-bg: #e5f1ff; --blue-border: #007aff;
  --gray-bg: #f0f0f5; --gray-text: #6e6e73;
  --purple: #af52de; --purple-bg: #f3e8fa; --purple-text: #7b2d9e;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-lg: 0 4px 12px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.04);
  --radius: 12px; --radius-sm: 8px;
  --hover-bg: #f5f5f7; --tab-active: #007aff; --tab-inactive: #86868b;
  --stripe: #fafafa;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #000000; --bg-secondary: #1c1c1e; --bg-card: #1c1c1e;
    --text-primary: #f5f5f7; --text-secondary: #a1a1a6; --text-tertiary: #6e6e73;
    --border: #38383a; --border-light: #2c2c2e;
    --green: #30d158; --green-bg: #0d3318; --green-text: #30d158;
    --red: #ff453a; --red-bg: #3a1511; --red-text: #ff453a;
    --amber: #ff9f0a; --amber-bg: #3a2a05; --amber-text: #ff9f0a;
    --blue: #0a84ff; --blue-bg: #0a1e3a; --blue-border: #0a84ff;
    --gray-bg: #2c2c2e; --gray-text: #a1a1a6;
    --purple: #bf5af2; --purple-bg: #2a1540; --purple-text: #bf5af2;
    --shadow: 0 1px 3px rgba(0,0,0,0.3);
    --shadow-lg: 0 4px 12px rgba(0,0,0,0.4);
    --hover-bg: #2c2c2e; --stripe: #141414;
  }}
}}
html[data-theme="dark"] {{
  --bg: #000000; --bg-secondary: #1c1c1e; --bg-card: #1c1c1e;
  --text-primary: #f5f5f7; --text-secondary: #a1a1a6; --text-tertiary: #6e6e73;
  --border: #38383a; --border-light: #2c2c2e;
  --green: #30d158; --green-bg: #0d3318; --green-text: #30d158;
  --red: #ff453a; --red-bg: #3a1511; --red-text: #ff453a;
  --amber: #ff9f0a; --amber-bg: #3a2a05; --amber-text: #ff9f0a;
  --blue: #0a84ff; --blue-bg: #0a1e3a; --blue-border: #0a84ff;
  --gray-bg: #2c2c2e; --gray-text: #a1a1a6;
  --purple: #bf5af2; --purple-bg: #2a1540; --purple-text: #bf5af2;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-lg: 0 4px 12px rgba(0,0,0,0.4);
  --hover-bg: #2c2c2e; --stripe: #141414;
}}
html[data-theme="light"] {{
  --bg: #ffffff; --bg-secondary: #f5f5f7; --bg-card: #ffffff;
  --text-primary: #1d1d1f; --text-secondary: #6e6e73; --text-tertiary: #86868b;
  --border: #d2d2d7; --border-light: #e8e8ed;
  --green: #34c759; --green-bg: #e8f9ed; --green-text: #1a7a2e;
  --red: #ff3b30; --red-bg: #ffeae9; --red-text: #c0291f;
  --amber: #ff9500; --amber-bg: #fff4e0; --amber-text: #996300;
  --blue: #007aff; --blue-bg: #e5f1ff; --blue-border: #007aff;
  --gray-bg: #f0f0f5; --gray-text: #6e6e73;
  --purple: #af52de; --purple-bg: #f3e8fa; --purple-text: #7b2d9e;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-lg: 0 4px 12px rgba(0,0,0,0.08), 0 1px 3px rgba(0,0,0,0.04);
  --hover-bg: #f5f5f7; --stripe: #fafafa;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', sans-serif;
  background: var(--bg); color: var(--text-primary);
  -webkit-font-smoothing: antialiased; line-height: 1.5;
}}
.header {{
  position: sticky; top: 0; z-index: 100; background: var(--bg);
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-light); padding: 16px 24px 0;
}}
@supports (backdrop-filter: blur(20px)) {{
  .header {{ background: color-mix(in srgb, var(--bg) 80%, transparent); }}
}}
.header-content {{ max-width: 1200px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}
.header h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -0.5px; font-family: 'SF Pro Display', 'Inter', sans-serif; }}
.header .meta {{ font-size: 14px; color: var(--text-secondary); font-weight: 500; display:flex; align-items:center; gap:12px; }}
.theme-toggle {{
  background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: 20px;
  padding: 4px 12px; cursor: pointer; font-size: 14px; color: var(--text-secondary);
  transition: all 0.2s;
}}
.theme-toggle:hover {{ background: var(--hover-bg); color: var(--text-primary); }}
.tabs {{ display: flex; gap: 0; margin-top: 12px; overflow-x: auto; -webkit-overflow-scrolling: touch; }}
.tab {{
  padding: 10px 18px; font-size: 14px; font-weight: 600; color: var(--tab-inactive);
  cursor: pointer; border-bottom: 2.5px solid transparent; transition: all 0.2s ease;
  white-space: nowrap; user-select: none;
}}
.tab:hover {{ color: var(--text-primary); }}
.tab.active {{ color: var(--tab-active); border-bottom-color: var(--tab-active); }}
.main {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

.summary-bar {{
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  padding: 14px 20px; margin-bottom: 20px;
  background: var(--bg-card); border: 1px solid var(--border-light);
  border-radius: var(--radius); box-shadow: var(--shadow);
  font-size: 14px; color: var(--text-secondary);
}}
.summary-bar .stat {{ font-weight: 600; color: var(--text-primary); }}
.summary-bar .divider {{ width: 1px; height: 20px; background: var(--border-light); }}
.src-badge {{
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600;
}}
.src-green {{ background: var(--green-bg); color: var(--green-text); }}
.src-amber {{ background: var(--amber-bg); color: var(--amber-text); }}
.src-red {{ background: var(--red-bg); color: var(--red-text); }}
.src-gray {{ background: var(--gray-bg); color: var(--gray-text); }}

.section {{
  background: var(--bg-card); border: 1px solid var(--border-light);
  border-radius: var(--radius); box-shadow: var(--shadow); margin-bottom: 20px; overflow: hidden;
}}
.section-header {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; cursor: pointer; user-select: none; transition: background 0.15s;
}}
.section-header:hover {{ background: var(--hover-bg); }}
.section-title {{ font-size: 17px; font-weight: 600; font-family: 'SF Pro Display', 'Inter', sans-serif; }}
.section-subtitle {{ font-size: 12px; font-weight: 400; color: var(--text-tertiary); margin-left: 8px; }}
.section-toggle {{ font-size: 14px; color: var(--text-tertiary); transition: transform 0.25s ease; }}
.section-body {{ padding: 0 20px 20px; }}
.section.collapsed .section-body {{ display: none; }}
.section.collapsed .section-toggle {{ transform: rotate(-90deg); }}

/* Tables — fixed column widths for alignment */
.table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
.table-wrap::-webkit-scrollbar {{ height: 6px; }}
.table-wrap::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 3px; }}
.data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; table-layout: fixed; }}
.data-table thead {{ position: sticky; top: 0; z-index: 2; }}
.data-table th {{
  padding: 10px 12px; text-align: right; font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-tertiary);
  background: var(--bg-card); border-bottom: 2px solid var(--border-light);
  white-space: nowrap; cursor: pointer; user-select: none;
  overflow: hidden; text-overflow: ellipsis;
}}
.data-table th:first-child {{ text-align: left; }}
.data-table th:hover {{ color: var(--text-primary); }}
.data-table th.sort-asc::after {{ content: " ↑"; }}
.data-table th.sort-desc::after {{ content: " ↓"; }}
.data-table td {{
  padding: 10px 12px; border-bottom: 1px solid var(--border-light);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.data-table tbody tr:hover {{ background: var(--hover-bg); }}
.data-table tbody tr:nth-child(even) {{ background: var(--stripe); }}
.data-table tbody tr:nth-child(even):hover {{ background: var(--hover-bg); }}

/* Column widths */
.data-table .ticker {{ text-align: left; width: 130px; min-width: 110px; }}
.data-table .num {{ text-align: right; font-variant-numeric: tabular-nums; font-feature-settings: "tnum"; }}
.data-table .price {{ font-weight: 600; }}

/* Fixed column widths for 7-col valuation table */
.data-table.cols-7 th:nth-child(1),
.data-table.cols-7 td:nth-child(1) {{ width: 130px; }}
.data-table.cols-7 th:nth-child(2),
.data-table.cols-7 td:nth-child(2) {{ width: 110px; }}
.data-table.cols-7 th:nth-child(3),
.data-table.cols-7 td:nth-child(3) {{ width: 70px; }}
.data-table.cols-7 th:nth-child(n+4),
.data-table.cols-7 td:nth-child(n+4) {{ width: 100px; }}
.data-table.cols-7 th:last-child,
.data-table.cols-7 td:last-child {{ width: 110px; }}

/* Fixed widths for 8-col bank table */
.data-table.cols-8 th:nth-child(1),
.data-table.cols-8 td:nth-child(1) {{ width: 130px; }}
.data-table.cols-8 th:nth-child(2),
.data-table.cols-8 td:nth-child(2) {{ width: 100px; }}
.data-table.cols-8 th:nth-child(3),
.data-table.cols-8 td:nth-child(3) {{ width: 65px; }}
.data-table.cols-8 th:nth-child(n+4),
.data-table.cols-8 td:nth-child(n+4) {{ width: 90px; }}
.data-table.cols-8 th:last-child,
.data-table.cols-8 td:last-child {{ width: 100px; }}

/* Fixed widths for 5-col quality/growth table */
.data-table.cols-5 th:nth-child(1),
.data-table.cols-5 td:nth-child(1) {{ width: 130px; }}
.data-table.cols-5 th:nth-child(2),
.data-table.cols-5 td:nth-child(2) {{ width: 110px; }}
.data-table.cols-5 th:nth-child(n+3),
.data-table.cols-5 td:nth-child(n+3) {{ width: 120px; }}

.ticker {{ font-weight: 600; }}
.name-sub {{ display: block; font-size: 11px; font-weight: 400; color: var(--text-tertiary); line-height: 1.2; }}
.val-green {{ color: var(--green); }}
.val-red {{ color: var(--red); }}

.badge {{ font-size: 10px; margin-left: 3px; cursor: help; vertical-align: middle; }}
.portfolio-dot {{ color: var(--blue); font-size: 8px; vertical-align: middle; margin-left: 4px; }}
.portfolio-row {{ background: var(--blue-bg) !important; }}

/* Median row */
.median-row {{ background: var(--blue-bg) !important; border-top: 2px solid var(--border); }}
.median-row:hover {{ background: var(--blue-bg) !important; }}
.median-label {{ font-weight: 700; color: var(--blue); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
.median-val {{ font-weight: 600; color: var(--blue); }}

/* Sector conclusions */
.sector-conclusion {{
  padding: 12px 16px; margin-bottom: 14px;
  background: var(--bg-secondary); border-radius: var(--radius-sm);
  font-size: 13px; line-height: 1.6; color: var(--text-secondary);
  border-left: 3px solid var(--blue);
}}

.source-vals {{ font-size: 12px; color: var(--text-secondary); font-family: 'SF Mono', 'Menlo', monospace; }}
.empty-msg {{ text-align: center; color: var(--text-tertiary); padding: 24px !important; font-style: italic; }}

.source-detail {{ margin-bottom: 16px; padding: 16px; background: var(--bg-secondary); border-radius: var(--radius-sm); }}
.source-detail h3 {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; }}
.source-detail .detail-meta {{ font-size: 13px; color: var(--text-secondary); }}
.notes-list {{ list-style: none; padding: 0; font-size: 13px; color: var(--text-secondary); }}
.notes-list li {{ padding: 4px 0; border-bottom: 1px solid var(--border-light); }}
.notes-list li:last-child {{ border-bottom: none; }}

.footer {{
  max-width: 1200px; margin: 0 auto; padding: 24px;
  font-size: 12px; color: var(--text-tertiary); text-align: center;
  border-top: 1px solid var(--border-light);
}}

@media (max-width: 768px) {{
  .header h1 {{ font-size: 22px; }}
  .header {{ padding: 12px 16px 0; }}
  .main {{ padding: 16px; }}
  .tab {{ padding: 8px 14px; font-size: 13px; }}
  .summary-bar {{ gap: 10px; padding: 12px 16px; font-size: 13px; }}
  .data-table {{ font-size: 13px; table-layout: auto; }}
  .data-table td, .data-table th {{ padding: 8px 10px; }}
}}

@media print {{
  .header {{ position: relative; }}
  .tab-content {{ display: block !important; }}
  .tabs, .theme-toggle {{ display: none; }}
  .section.collapsed .section-body {{ display: block; }}
}}
</style>
</head>
<body>

<div class="header">
  <div class="header-content">
    <div>
      <h1>🇷🇺 Russian Portfolio</h1>
      <div class="meta">{date_str} · {time_str}</div>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()" title="Toggle dark/light mode">🌓</button>
  </div>
  <div class="tabs" style="max-width:1200px; margin:0 auto;">
    <div class="tab active" onclick="switchTab(this, 'portfolio')">Portfolio</div>
    <div class="tab" onclick="switchTab(this, 'sectors')">Sectors</div>
    <div class="tab" onclick="switchTab(this, 'audit')">Audit</div>
    <div class="tab" onclick="switchTab(this, 'sources')">Sources</div>
  </div>
</div>

<div class="main">

  <div class="summary-bar">
    <span><span class="stat">{len(PORTFOLIO)}</span> stocks</span>
    <span class="divider"></span>
    <span>Verified: <span class="stat">{confidence_pct:.0f}%</span></span>
    <span class="divider"></span>
    <span style="font-size:12px;">✅ {verified_count} cross-checked · <span style="color:var(--text-tertiary)">· {single_count} single-source</span>{f' · 🔴 {divergent_count} divergent' if divergent_count else ''}</span>
    <span class="divider"></span>
    <span>{source_badges}</span>
  </div>

  <!-- ═══ PORTFOLIO TAB ═══ -->
  <div class="tab-content active" id="tab-portfolio">

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">📊 Valuation</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table sortable cols-7">
            <thead><tr>
              <th>Ticker</th><th>Price</th><th>Chg</th><th>P/E</th><th>EV/EBITDA</th><th>P/S</th><th>Mkt Cap</th>
            </tr></thead>
            <tbody>{portfolio_valuation}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">🏦 Banks</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table sortable cols-8">
            <thead><tr>
              <th>Ticker</th><th>Price</th><th>Chg</th><th>P/E</th><th>P/BV</th><th>ROE</th><th>Div Yield</th><th>Mkt Cap</th>
            </tr></thead>
            <tbody>{portfolio_banks_html}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">💎 Quality</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table sortable cols-5">
            <thead><tr>
              <th>Ticker</th><th>Price</th><th>Net Margin</th><th>ROE</th><th>Div Yield</th>
            </tr></thead>
            <tbody>{portfolio_quality}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">📈 Growth<span class="section-subtitle">{fy_label}</span></span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table sortable cols-5">
            <thead><tr>
              <th>Ticker</th><th>Price</th><th>Revenue</th><th>EBITDA</th><th>Net Income</th>
            </tr></thead>
            <tbody>{portfolio_growth}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">🧾 Financials<span class="section-subtitle">{fy_fin_label}, ₽B</span></span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table sortable cols-7">
            <thead><tr>
              <th>Ticker</th><th>Price</th><th>Revenue</th><th>EBITDA</th><th>Net Income</th><th>Net Debt</th><th>ND/EBITDA</th>
            </tr></thead>
            <tbody>{portfolio_financials}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">📅 Upcoming Dividends</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table" style="table-layout:auto">
            <thead><tr>
              <th>Ticker</th><th>Record Date</th><th>Amount</th><th>TTM Yield</th>
            </tr></thead>
            <tbody>{dividend_calendar_html}</tbody>
          </table>
        </div>
      </div>
    </div>

  </div>

  <!-- ═══ SECTORS TAB ═══ -->
  <div class="tab-content" id="tab-sectors">
    {sectors_html}
  </div>

  <!-- ═══ AUDIT TAB ═══ -->
  <div class="tab-content" id="tab-audit">
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">🔍 Data Divergence Report</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div class="table-wrap">
          <table class="data-table" style="table-layout:auto">
            <thead><tr>
              <th style="width:30px"></th><th>Ticker</th><th>Metric</th><th>Spread</th><th>Source Values</th>
            </tr></thead>
            <tbody>{audit_html}</tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- ═══ SOURCES TAB ═══ -->
  <div class="tab-content" id="tab-sources">
    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">🔌 Source Health</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap:12px;">
          <div class="source-detail" style="border-left: 3px solid var(--blue);">
            <h3>T-Bank Invest API <span style="font-size:11px;color:var(--blue);font-weight:400;">PRIMARY</span></h3>
            <p class="detail-meta">Licensed broker · P/E, P/BV, P/S, ROE, Revenue, Net Income, EPS, Dividends, Beta, Growth</p>
            <p style="margin-top:8px;">{source_health["tbank"]["ok"]} OK / {source_health["tbank"]["fail"]} failed</p>
          </div>
          <div class="source-detail">
            <h3>MOEX ISS API</h3>
            <p class="detail-meta">Official exchange · Prices, market cap, dividends (trailing 12m), 52w range</p>
            <p style="margin-top:8px;">{source_health["moex"]["ok"]} OK / {source_health["moex"]["fail"]} failed</p>
          </div>
          <div class="source-detail">
            <h3>smart-lab.ru</h3>
            <p class="detail-meta">Cross-check · IFRS annual fundamentals · {fy_fin_label} reports</p>
            <p style="margin-top:8px;">{source_health["smartlab"]["ok"]} OK / {source_health["smartlab"]["fail"]} failed</p>
          </div>
          <div class="source-detail">
            <h3>Tradernet (Freedom Finance)</h3>
            <p class="detail-meta">Cross-check · Price, 52-week range · Real-time</p>
            <p style="margin-top:8px;">{source_health["tradernet"]["ok"]} OK / {source_health["tradernet"]["fail"]} failed</p>
          </div>
          <div class="source-detail">
            <h3>dohod.ru</h3>
            <p class="detail-meta">Cross-check · Dividend yield, DSI, payout ratio, forecasts</p>
            <p style="margin-top:8px;">{source_health["dohod"]["ok"]} OK / {source_health["dohod"]["fail"]} failed</p>
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">📋 Data Period</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <ul class="notes-list">
          <li><strong>Fundamentals</strong>: T-Bank Invest API (TTM), cross-checked with smart-lab.ru ({fy_fin_label} IFRS)</li>
          <li><strong>Growth</strong>: T-Bank (1Y revenue growth) + smart-lab ({fy_label})</li>
          <li><strong>Prices</strong>: MOEX TQBR (primary), cross-checked with Tradernet + T-Bank</li>
          <li><strong>Dividends</strong>: T-Bank + MOEX trailing 12m + smart-lab + dohod.ru (4 sources)</li>
          <li><strong>Valuation</strong>: T-Bank TTM (primary), smart-lab LTM (cross-check)</li>
          <li><strong>52-week range</strong>: MOEX historical + T-Bank + Tradernet (3 sources)</li>
          <li><strong>Dashboard generated</strong>: {generated_at.strftime("%Y-%m-%d %H:%M:%S")} MSK</li>
        </ul>
      </div>
    </div>

    <div class="section">
      <div class="section-header" onclick="toggleSection(this)">
        <span class="section-title">⚠️ Notes & Warnings</span>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <ul class="notes-list">
          {notes_html}
        </ul>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  Generated {generated_at.strftime("%Y-%m-%d %H:%M:%S")} MSK · Fundamentals: {fy_fin_label} · 5 sources · T-Bank primary + cross-validated
</div>

<script>
function switchTab(el, tabId) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('tab-' + tabId).classList.add('active');
}}
function toggleSection(header) {{
  header.parentElement.classList.toggle('collapsed');
}}
function toggleTheme() {{
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  if (current === 'dark') html.setAttribute('data-theme', 'light');
  else if (current === 'light') html.removeAttribute('data-theme');
  else html.setAttribute('data-theme', 'dark');
}}
document.querySelectorAll('.sortable th').forEach(th => {{
  th.addEventListener('click', function() {{
    const table = this.closest('table');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const idx = Array.from(this.parentElement.children).indexOf(this);
    const isAsc = this.classList.contains('sort-asc');
    this.parentElement.querySelectorAll('th').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
    this.classList.add(isAsc ? 'sort-desc' : 'sort-asc');
    rows.sort((a, b) => {{
      let aT = a.children[idx]?.textContent?.trim() || '';
      let bT = b.children[idx]?.textContent?.trim() || '';
      let aM = 1, bM = 1;
      if (aT.includes('T')) aM = 1e12; else if (aT.includes('B')) aM = 1e9; else if (aT.includes('M')) aM = 1e6;
      if (bT.includes('T')) bM = 1e12; else if (bT.includes('B')) bM = 1e9; else if (bT.includes('M')) bM = 1e6;
      let aN = parseFloat(aT.replace(/[₽,%xTBM+\\s]/g, '').replace(/,/g, ''));
      let bN = parseFloat(bT.replace(/[₽,%xTBM+\\s]/g, '').replace(/,/g, ''));
      if (aM > 1) aN *= aM; if (bM > 1) bN *= bM;
      if (!isNaN(aN) && !isNaN(bN)) return isAsc ? bN - aN : aN - bN;
      return isAsc ? bT.localeCompare(aT) : aT.localeCompare(bT);
    }});
    rows.forEach(r => tbody.appendChild(r));
  }});
}});
</script>
</body>
</html>'''
