# Russian Portfolio Dashboard v2 — Runbook

> Read this file before doing ANY work on this project.

## Quick Reference
| Task | Command / Steps |
|------|----------------|
| Generate dashboard | `cd /Users/iibot/Documents/ppppp/workspace/ru-portfolio-dashboard && python -m src.dashboard` |
| Generate to specific path | `python -m src.dashboard --output /path/to/output.html` |
| Check LaunchAgent | `launchctl list \| grep ru-dashboard` |
| Reload LaunchAgent | `launchctl unload ~/Library/LaunchAgents/com.lopushokbot.ru-dashboard.plist && launchctl load ~/Library/LaunchAgents/com.lopushokbot.ru-dashboard.plist` |
| View live site | https://lopushokbot.github.io/ru-portfolio-dashboard/ |
| Check logs | `ls -la /Users/iibot/Documents/ppppp/archive/portfolio-dashboard-v2/logs/` |

---

## Task: Weekly Dashboard Update

### When to run
- Automatically every Sunday 9:00 AM Dubai via LaunchAgent
- Manually if auto-update fails or data needs refresh

### Prerequisites
- Python 3 with `requests`, `beautifulsoup4`, `lxml` installed (`pip install -r requirements.txt`)
- `.env` file exists with valid `TBANK_TOKEN` (chmod 600)
- Internet access

### Steps
1. Navigate to project:
   ```bash
   cd /Users/iibot/Documents/ppppp/archive/portfolio-dashboard-v2
   ```
2. Verify `.env` exists and has the token:
   ```bash
   test -f .env && echo "OK" || echo "MISSING .env"
   ```
3. Run the dashboard generator:
   ```bash
   python -m src.dashboard
   ```
4. Script flow:
   - Fetches all 5 sources in parallel (ThreadPoolExecutor)
   - T-Bank API: uses Bearer token from `.env`
   - smart-lab.ru: scraped with 0.7-1s polite delays
   - Cross-validates all data points across sources
   - Flags discrepancies above thresholds (35% ratio / 15pp percentage / 30% absolute)
   - Generates self-contained HTML with Apple-style design
5. Output goes to `output/` directory
6. Auto-push to GitHub Pages (if running via LaunchAgent)

### Validation
- [ ] Open generated HTML in browser
- [ ] All 10 portfolio stocks + peers are shown
- [ ] Each stock has price, P/E, P/BV, dividends, and other fundamentals
- [ ] Cross-validation warnings are reasonable (not flagging everything)
- [ ] "Generated at" timestamp is current
- [ ] Sector comparison tables are complete

### If something goes wrong
| Symptom | Cause | Fix |
|---------|-------|-----|
| T-Bank returns 401 | Token expired or invalid | Get new read-only token from T-Bank app, update `.env` |
| smart-lab timeout on MGNT | Their server is slow for this ticker | Re-run — has retry logic; if persistent, skip MGNT temporarily |
| MOEX returns empty data | Market is closed / holiday | Normal on weekends before Sunday open; data will be from last trading day |
| Cross-validation flags everything | T-Bank TTM vs smart-lab annual mismatch | Check if thresholds need widening in `config.py` |
| LaunchAgent not running | Mac was asleep / agent unloaded | `launchctl load ~/Library/LaunchAgents/com.lopushokbot.ru-dashboard.plist` |
| `ModuleNotFoundError` | Dependencies not installed | `pip install -r requirements.txt` |

---

## Task: Add a New Stock to Portfolio

### Steps
1. In `src/config.py`:
   - Add ticker to `PORTFOLIO` list
   - Add to the correct sector in `SECTORS`
   - Add display name to `TICKER_NAMES`
   - Check if MOEX uses a different ticker (like TCSG → T) — add mapping if needed
2. Test: `python -m src.dashboard`
3. Verify the new stock appears with data from all 5 sources
4. Check cross-validation isn't flagging it incorrectly
5. Update this RUNBOOK.md and CLAUDE.md
6. Commit and push

---

## Task: Update T-Bank Token

### Steps
1. Get new read-only token from T-Bank Invest app/website
2. Update the `.env` file:
   ```bash
   echo "TBANK_TOKEN=new_token_here" > /Users/iibot/Documents/ppppp/archive/portfolio-dashboard-v2/.env
   chmod 600 /Users/iibot/Documents/ppppp/archive/portfolio-dashboard-v2/.env
   ```
3. Test: `python -m src.dashboard`
4. Verify T-Bank data is coming through (check logs)

### Security rules
- NEVER commit `.env` to git
- NEVER put the token in CLAUDE.md, RUNBOOK.md, or any tracked file
- NEVER send the token to any external service or API other than T-Bank
- Token permissions should be READ-ONLY

---

## Task: Fix a Broken Data Source

### Steps
1. Identify which source is failing from logs or dashboard output
2. Test the source individually:
   - T-Bank: Check token validity, API status
   - MOEX: `curl -s "https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER.json" | python -m json.tool | head -20`
   - smart-lab: Open `https://smart-lab.ru/q/SBER/f/y/` in browser, check if structure changed
   - Tradernet: `curl -s "https://tradernet.com/securities/export?tickers=SBER" | python -m json.tool | head -20`
   - dohod.ru: Open `https://www.dohod.ru/ik/analytics/dividend/sber` in browser
3. Common fixes:
   - **HTML structure changed** (smart-lab/dohod): Update CSS selectors in scraper
   - **API endpoint changed**: Update URL in source file
   - **Rate limited**: Increase delay between requests
4. Test full pipeline after fix
5. Update Known Issues in CLAUDE.md

---

## Changelog
| Date | Change |
|------|--------|
| 2026-04-14 | v2 completed — 5 sources with cross-validation, LaunchAgent automation |
