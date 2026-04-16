# Russian Portfolio Dashboard v2

## Overview
Weekly auto-updating Russian stock portfolio dashboard. Tracks 10 stocks + 10 benchmark peers across 5 sectors. Fetches fundamentals from 5 Russian data sources with cross-validation, generates a self-contained HTML dashboard, auto-deploys to GitHub Pages every Sunday.

## Live URLs
| Environment | URL |
|-------------|-----|
| Live | https://lopushokbot.github.io/ru-portfolio-dashboard/ |
| GitHub | https://github.com/lopushokbot/ru-portfolio-dashboard |
| Local path | `/Users/iibot/Documents/ppppp/workspace/ru-portfolio-dashboard/` |

## Tech Stack
- Python 3 with `requests`, `beautifulsoup4`, `lxml`
- Dependencies in `requirements.txt`
- macOS LaunchAgent for weekly automation
- Static HTML output (single file, self-contained)

## Architecture
```
archive/portfolio-dashboard-v2/
├── src/
│   ├── config.py              # Portfolio tickers, sectors, names, thresholds
│   ├── dashboard.py           # Main orchestrator — fetches, validates, renders
│   ├── sources/
│   │   ├── tbank.py           # T-Bank Invest API (PRIMARY for fundamentals)
│   │   ├── moex.py            # MOEX ISS API (prices, market cap, dividends)
│   │   ├── smartlab.py        # smart-lab.ru scraper (IFRS cross-check)
│   │   ├── tradernet.py       # Tradernet API (price cross-check)
│   │   ├── dohod.py           # dohod.ru scraper (dividend cross-check)
│   │   ├── finrange.py        # (unused — was planned, not implemented)
│   │   └── yahoo_ru.py        # (unused — Yahoo data is wrong post-sanctions)
│   ├── engine/
│   │   └── validator.py       # Cross-validation engine (5-source comparison)
│   └── render/
│       └── html_builder.py    # HTML generation with Apple-style design
├── output/                    # Generated HTML output
├── logs/                      # Execution logs
├── .env                       # T-Bank API token (local only, gitignored, chmod 600)
└── scripts/                   # Utility scripts
```

## Data Sources
| # | Source | Type | Auth | Primary Use |
|---|--------|------|------|------------|
| 1 | **T-Bank Invest API** | REST | Bearer token (`.env`) | PRIMARY — P/E, P/BV, P/S, ROE, Revenue, Net Income, EPS, Dividends, Beta, 52w range |
| 2 | **MOEX ISS API** | REST | None | Prices, market cap, dividends (trailing 12m), 52w historical candles |
| 3 | **smart-lab.ru** | HTML scraping | None | IFRS annual fundamentals cross-check, balance sheet, YoY growth |
| 4 | **Tradernet** | REST | None | Price cross-check, 52w range |
| 5 | **dohod.ru** | HTML scraping | None | Dividend yield cross-check, DSI, forecasts |

**DO NOT use Yahoo Finance** for Russian stocks — post-sanctions data is wrong (prices off 30-130%).

## Portfolio
| Ticker | Name | Sector |
|--------|------|--------|
| YDEX | Yandex | Tech |
| TCSG | T-Technologies | Banks/Fintech |
| LKOH | LUKOIL | Oil & Gas |
| HEAD | HeadHunter | Tech |
| SBER | Sberbank | Banks/Fintech |
| X5 | X5 Group | Retail |
| NVTK | NOVATEK | Oil & Gas |
| GMKN | Norilsk Nickel | Metals & Mining |
| CNRU | CIAN | Tech |
| TATN | Tatneft | Oil & Gas |

Peers: ROSN, GAZP, VTBR, BSPB, NLMK, MAGN, CHMF, MGNT, OZON, VK

## Deployment
- **Automated**: macOS LaunchAgent at `~/Library/LaunchAgents/com.lopushokbot.ru-dashboard.plist`
- **Schedule**: Every Sunday 9:00 AM Dubai time
- **Process**: Runs locally on Mac, pushes generated HTML to GitHub Pages
- **Why local, not cloud**: T-Bank token stays on the machine, no cloud exposure

## Environment Variables
| Variable | Purpose | Where stored |
|----------|---------|-------------|
| `TBANK_TOKEN` | T-Bank Invest API read-only token | `.env` file (chmod 600, gitignored) |

## Known Issues & Gotchas
- **MOEX ticker mapping**: TCSG = `T` on MOEX, VK = `VKCO` — mapped in `config.py`
- **smart-lab.ru scraping**: LTM row sometimes duplicates last fiscal year; TCSG listed as "T"; occasional timeouts (especially MGNT)
- **Cross-validation thresholds**: 35% ratio, 15pp percentage, 30% absolute — widened because T-Bank TTM vs smart-lab annual IFRS always differ
- **Security**: `html.escape()` on all external data; error messages show only exception type, never `str(e)`; dependencies pinned
