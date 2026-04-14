# Russian Portfolio Dashboard v2 — Project Plan

> **Goal**: A production-grade Russian stock portfolio dashboard with maximum data accuracy through multi-source cross-validation. Every number is verified. Stock price captured at the moment of generation.

---

## Portfolio (10 tickers)

| Ticker | Name | Sector |
|--------|------|--------|
| YDEX | Яндекс | Tech/Internet |
| TCSG | Т-Технологии | Banks/Fintech |
| LKOH | ЛУКОЙЛ | Oil & Gas |
| HEAD | HeadHunter | Tech/Internet |
| SBER | Сбербанк | Banks/Fintech |
| X5 | X5 Group | Retail |
| NVTK | НОВАТЭК | Oil & Gas |
| GMKN | Норильский никель | Metals & Mining |
| CNRU | ЦИАН | Tech/Internet |
| TATN | Татнефть | Oil & Gas |

### Benchmark Peers (for sector comparison)

| Sector | Portfolio | + Peers |
|--------|-----------|---------|
| 🛢️ Oil & Gas | LKOH, NVTK, TATN | ROSN, GAZP |
| 🏦 Banks/Fintech | SBER, TCSG | VTBR, BSPB |
| ⛏️ Metals & Mining | GMKN | NLMK, MAGN, CHMF |
| 🛒 Retail | X5 | MGNT, OZON |
| 💻 Tech/Internet | YDEX, HEAD, CNRU | VK |

---

## 1. Data Sources — Russian Reality

Russian market has fewer API options than US. Here's the realistic picture:

### Source 1: MOEX ISS API (Official Exchange)
- **Type**: JSON REST API, no auth needed
- **Reliability**: Gold standard for market data
- **Provides**: Real-time price, market cap, issue size, dividends (registry data), trading volume
- **Ticker mapping**: TCSG → T, VK → VKCO on MOEX
- **Rate limits**: Generous, no key needed

### Source 2: smart-lab.ru (Community Fundamentals)
- **Type**: HTML scraping (BeautifulSoup)
- **Reliability**: High, widely used by Russian investors
- **Provides**: P/E, EV/EBITDA, P/BV, P/S, ROE, Net Margin, Revenue, EBITDA, Net Income, Net Debt, Dividend Yield, YoY growth rates (all IFRS annual)
- **Quirks**: LTM row sometimes duplicates last fiscal year; TCSG listed as "T"; occasional timeouts (MGNT)
- **Rate limits**: Polite scraping with 0.7-1s delays

### Source 3: Yahoo Finance (yfinance, .ME suffix) — NEW
- **Type**: Python API (`yfinance`), no auth
- **Reliability**: Good for major Russian stocks, spotty for small-caps
- **Provides**: P/E (trailing + forward), P/B, Market Cap, Revenue, Net Income, EBITDA, Dividend Yield, 52-week range, daily price change
- **Ticker format**: `SBER.ME`, `LKOH.ME`, `GAZP.ME`, etc.
- **Gaps**: May not have CNRU, some metrics lag by quarters
- **Value**: International data source — independent from Russian platforms

### Source 4: Finrange.com — NEW
- **Type**: HTML scraping (needs Playwright for JS rendering)
- **Reliability**: Good, professional service covering MOEX
- **Provides**: P/E, Dividend Yield, Market Cap, Revenue trends, EBITDA, financial ratios
- **URL pattern**: `finrange.com/en/company/MOEX/{TICKER}`
- **Rate limits**: Moderate, 1-2s per page load
- **Value**: Third independent fundamentals source

### Source Summary Matrix

| Metric | MOEX | smart-lab | Yahoo (.ME) | Finrange |
|--------|------|-----------|-------------|----------|
| Price | ✅ primary | — | ✅ cross-check | — |
| Market Cap | ✅ | — | ✅ cross-check | ✅ |
| P/E | — | ✅ primary | ✅ cross-check | ✅ cross-check |
| EV/EBITDA | — | ✅ primary | — | ✅ cross-check |
| P/BV | — | ✅ primary | ✅ cross-check | — |
| P/S | — | ✅ primary | ✅ cross-check | — |
| ROE | — | ✅ primary | ✅ cross-check | — |
| Net Margin | — | ✅ primary | ✅ (calc from data) | — |
| Revenue | — | ✅ (₽B) | ✅ cross-check | ✅ cross-check |
| EBITDA | — | ✅ (₽B) | ✅ cross-check | ✅ cross-check |
| Net Income | — | ✅ (₽B) | ✅ cross-check | — |
| Net Debt | — | ✅ (₽B) | ✅ (calc from BS) | — |
| Dividend Yield | ✅ (LTM) | ✅ | ✅ cross-check | ✅ cross-check |
| Revenue YoY | — | ✅ (calc) | ✅ (calc) | — |
| EBITDA YoY | — | ✅ (calc) | — | — |
| 52-Week Range | — | — | ✅ | — |
| Daily Change | ✅ | — | ✅ | — |

---

## 2. Cross-Validation Engine

### How It Works

```
For each metric M and stock S:
  1. Collect M from all sources that report it (2-4 values)
  2. If only 1 source → display with "single source" note
  3. If 2+ sources:
     a. Calculate median
     b. Check divergence thresholds:
        - Ratios (P/E, EV/EBITDA, P/B, P/S): flag if >20% relative spread
        - Percentages (margins, ROE, yields): flag if >10pp absolute spread
        - Absolute ₽ values (revenue, debt): flag if >15% relative spread
     c. Assign confidence:
        ✅ Confirmed — all sources agree within threshold
        ⚠️ Check — one outlier, median still reliable
        🔴 Divergence — major disagreement, investigate
  4. Display median value with confidence badge
  5. Hover tooltip: "MOEX: X | smart-lab: Y | Yahoo: Z"
```

### Known Gotchas for Russian Data
- **IFRS vs RSBU**: smart-lab uses IFRS (МСФО) annual reports. Yahoo may mix periods. Always prefer IFRS.
- **Currency**: All in RUB. Yahoo reports in RUB for .ME tickers but verify.
- **Fiscal year alignment**: Most Russian companies report Jan-Dec. Some (X5) have fiscal year quirks.
- **LTM duplication**: smart-lab sometimes shows last FY as LTM — must dedupe for growth calculations.
- **Banks**: P/B is the primary valuation metric, not EV/EBITDA (which is meaningless for banks).
- **Sanctions impact**: Some tickers may have gaps in Yahoo Finance post-2022.

---

## 3. Metrics to Display

### Per-Stock Row (NEW: price always visible)

| Category | Metric | Primary Source | Cross-check |
|----------|--------|---------------|-------------|
| **Price** | Current Price (₽) | MOEX | Yahoo |
| **Price** | Daily Change (%) | MOEX | Yahoo |
| **Price** | 52-Week Range | Yahoo | — |
| **Valuation** | P/E | smart-lab | Yahoo, Finrange |
| **Valuation** | EV/EBITDA | smart-lab | Finrange |
| **Valuation** | P/BV | smart-lab | Yahoo |
| **Quality** | Net Margin | smart-lab | Yahoo (calc) |
| **Quality** | ROE | smart-lab | Yahoo |
| **Quality** | Dividend Yield | MOEX | smart-lab, Yahoo, Finrange |
| **Growth** | Revenue YoY | smart-lab (calc) | Yahoo (calc) |
| **Growth** | EBITDA YoY | smart-lab (calc) | — |
| **Growth** | Net Income YoY | smart-lab (calc) | — |
| **Balance Sheet** | Revenue (₽B) | smart-lab | Yahoo, Finrange |
| **Balance Sheet** | EBITDA (₽B) | smart-lab | Yahoo, Finrange |
| **Balance Sheet** | Net Income (₽B) | smart-lab | Yahoo |
| **Balance Sheet** | Net Debt (₽B) | smart-lab | Yahoo (calc) |
| **Balance Sheet** | ND/EBITDA | smart-lab (calc) | — |
| **Market** | Market Cap | MOEX | Yahoo, Finrange |

### Special Rules
- **Banks** (SBER, TCSG, VTBR, BSPB): Show P/BV as primary valuation; EV/EBITDA hidden
- **Loss-making companies**: P/E shown as "neg", EV/EBITDA as N/A if negative
- **Missing data**: Gray "N/A" with note in Data tab explaining why

---

## 4. Design System

### Visual Language
Same Apple-inspired design as v1, but enhanced.

### Typography

| Element | Font | Size | Weight |
|---------|------|------|--------|
| Page title | SF Pro Display | 28px | 700 |
| Date + timestamp | Inter | 15px | 500 |
| Section headers | SF Pro Display | 17px | 600 |
| Table headers | Inter | 12px | 600, uppercase, tracking |
| Table body | Inter | 14px | 400 |
| Price display | SF Pro Display | 16px | 600 |
| Badges | Inter | 11px | 600 |
| Tooltips | Inter | 12px | 400 |

### Color Tokens (Light / Dark)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| --bg | #ffffff | #000000 | Page |
| --bg-card | #ffffff | #1c1c1e | Cards |
| --bg-secondary | #f5f5f7 | #1c1c1e | Alt rows |
| --green | #34c759 | #30d158 | Positive, confirmed ✅ |
| --red | #ff3b30 | #ff453a | Negative, divergence 🔴 |
| --amber | #ff9500 | #ff9f0a | Warning ⚠️ |
| --blue | #007aff | #0a84ff | Active tabs, links |
| --purple | #af52de | #bf5af2 | Portfolio highlights |

### Layout

```
+--------------------------------------------------+
| 🇷🇺 Russian Portfolio    Apr 13, 2026 15:42 MSK  |
| [Portfolio] [Sectors] [Audit] [Sources]           |
+--------------------------------------------------+

TAB: Portfolio
+--------------------------------------------------+
| SUMMARY BAR                                       |
| 10 stocks · 20 total w/ peers                     |
| Sources: MOEX ✅  smart-lab ✅  Yahoo ✅  Finrange ✅|
| Data confidence: 94%                              |
+--------------------------------------------------+
|                                                   |
| VALUATION (collapsible)                           |
| ┌──────┬────────┬───────┬───────┬─────────┬─────┐|
| │Ticker│Price ₽ │ Chg%  │ P/E   │EV/EBITDA│ P/BV│|
| │SBER  │₽303.50 │+1.2%  │ 5.1x✅│  —      │0.9x✅│|
| │LKOH  │₽7,120  │-0.3%  │40.4x⚠️│ 6.2x✅  │1.8x✅│|
| └──────┴────────┴───────┴───────┴─────────┴─────┘|
|                                                   |
| QUALITY (collapsible)                             |
| GROWTH (collapsible)                              |
| FINANCIALS (collapsible)                          |
| BALANCE SHEET (collapsible)                       |
+--------------------------------------------------+

TAB: Sectors (5 sector comparison tables with peers)
TAB: Audit (every flagged divergence with source values)
TAB: Sources (health status, timestamps, errors per source)
```

### Interactive Elements
- Collapsible sections (smooth CSS transition)
- Sticky header with frosted glass blur
- Tab navigation
- Hover: row highlight + tooltip showing per-source breakdown
- Dark/light: auto (`prefers-color-scheme`) + manual toggle button
- Click-to-sort on any column header
- Portfolio tickers highlighted (bold/accent) in sector tables

---

## 5. Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python 3.11+ | Matches v1, rich ecosystem |
| Market data | MOEX ISS API (requests) | Official, JSON, no auth |
| Fundamentals | smart-lab (BeautifulSoup) | Best Russian IFRS data |
| Cross-check 1 | yfinance (.ME tickers) | Independent intl source |
| Cross-check 2 | Finrange (Playwright) | Third Russian source |
| Parallelism | ThreadPoolExecutor | Concurrent fetching |
| Output | Single self-contained HTML | Zero runtime deps |
| Hosting | GitHub Pages | Already set up |

### Dependencies
```
requests
beautifulsoup4
lxml
yfinance
playwright  # for Finrange scraping
```

---

## 6. Features — Build Blocks

### Block 1: Data Engine (Core)
- [ ] MOEX ISS fetcher — price, market cap, dividends, volume
- [ ] smart-lab scraper — all IFRS fundamentals (keep existing logic, harden)
- [ ] Yahoo Finance fetcher — .ME tickers, P/E, P/B, revenue, margins, 52w range
- [ ] Finrange scraper (Playwright) — P/E, div yield, revenue, market cap
- [ ] Price snapshot — capture exact price + timestamp at generation
- [ ] Ticker mapping layer — handle TCSG→T, VK→VKCO across all sources
- [ ] Caching — avoid refetching within same run
- [ ] Graceful degradation — if Yahoo or Finrange is down, continue with 2 sources

### Block 2: Validation & Processing
- [ ] Cross-validation engine — median, divergence detection, confidence badges
- [ ] IFRS consistency check — ensure all sources report same fiscal period
- [ ] Bank-specific rules — P/BV primary, no EV/EBITDA
- [ ] Growth calculation — YoY from historical data, LTM deduplication
- [ ] Sanity checks — P/E positive or N/A, margins in range, debt sign check
- [ ] Audit log — record every divergence with source values
- [ ] Sector classification with portfolio highlighting

### Block 3: HTML Renderer
- [ ] Sticky header with tabs (Portfolio / Sectors / Audit / Sources)
- [ ] Summary bar — stock count, source health, overall confidence %
- [ ] Valuation table with price column
- [ ] Quality table (margins, ROE, dividend yield)
- [ ] Growth table (revenue, EBITDA, net income YoY)
- [ ] Financials table (₽B absolute values)
- [ ] Balance sheet table (net debt, ND/EBITDA)
- [ ] 5 sector comparison tables
- [ ] Audit tab — divergence report
- [ ] Sources tab — per-source health, timestamps, error log
- [ ] Confidence badges inline (✅ / ⚠️ / 🔴)
- [ ] Hover tooltips with per-source values

### Block 4: Design Polish
- [ ] CSS variables with dark/light mode
- [ ] SF Pro Display + Inter typography
- [ ] Manual dark mode toggle
- [ ] Click-to-sort columns
- [ ] Smooth collapse/expand animations
- [ ] Responsive mobile layout (horizontal scroll tables)
- [ ] Portfolio ticker highlighting in sector tables
- [ ] Print-friendly styles
- [ ] "Generated at" timestamp in footer

### Block 5: Deployment
- [ ] GitHub repo (update existing `lopushokbot/portfolio-dashboard`)
- [ ] GitHub Pages deployment
- [ ] Run script (`scripts/run_ru_v2.sh`)
- [ ] SEO basics (OG tags, meta, favicon)
- [ ] Integration with existing daily-dashboards workflow

---

## 7. What's New vs v1

| Aspect | v1 (current) | v2 (new) |
|--------|-------------|----------|
| Data sources | 2 (MOEX + smart-lab) | 4 (+ Yahoo + Finrange) |
| Cross-validation | None | Full median + confidence scoring |
| Price display | Not shown in tables | Price + change + 52w range in every table |
| Transparency | Notes at bottom | Dedicated Audit tab + inline badges + tooltips |
| Sorting | None | Click-to-sort any column |
| Dark mode | Auto only | Auto + manual toggle |
| Source monitoring | Error notes | Dedicated Sources tab with health status |

---

## 8. File Structure

```
portfolio-dashboard-v2/
├── src/
│   ├── dashboard.py            # Main orchestrator
│   ├── sources/
│   │   ├── moex.py             # MOEX ISS API
│   │   ├── smartlab.py         # smart-lab.ru scraper
│   │   ├── yahoo_ru.py         # yfinance .ME wrapper
│   │   └── finrange.py         # Finrange Playwright scraper
│   ├── engine/
│   │   ├── validator.py        # Cross-validation + confidence
│   │   ├── normalizer.py       # Unit/period normalization
│   │   └── sectors.py          # Sector config + peer mapping
│   └── render/
│       ├── html_builder.py     # HTML generation
│       ├── styles.py           # CSS as Python string
│       └── scripts.py          # JS as Python string
├── output/
│   └── ru_portfolio_dashboard.html
├── logs/
├── scripts/
│   └── run.sh
├── requirements.txt
└── README.md
```

---

## 9. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Yahoo Finance blocks .ME tickers | Lose 1 cross-check source | Graceful fallback to 2 sources, log warning |
| smart-lab HTML structure changes | Lose primary fundamentals | Versioned selectors, alert on parse failure |
| Finrange requires heavy JS rendering | Slow, brittle | Playwright with retry + timeout, run last |
| MOEX API downtime | No prices | Cache last known price, show "stale" badge |
| Sanctions-related data gaps | Missing metrics for some tickers | Show N/A transparently, never guess |
| LTM / fiscal year mismatch | Wrong YoY growth | Explicit period labels, dedupe logic from v1 |

---

## Next Step

Once you approve this plan, I start building Block 1 (Data Engine) immediately.
