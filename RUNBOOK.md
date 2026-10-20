# Russian Portfolio Valuation Dashboard — Runbook

> Read this before any work on the project. Update the Log at the bottom after every change.

## Quick reference

| Task | Command |
|------|---------|
| Refresh data now (no publish) | `cd ~/ru-portfolio-dashboard && node scripts/update.mjs` |
| Refresh + publish now | `cd ~/ru-portfolio-dashboard && FORCE_RUN=1 ./run.sh; tail -30 logs/run-$(date +%F).log` |
| View locally | `cd ~/ru-portfolio-dashboard && python3 -m http.server 8735` → http://localhost:8735/ |
| Check today's run | `cat ~/ru-portfolio-dashboard/logs/run-$(date +%F).log` |
| LaunchAgent status | `launchctl list \| grep ru-dashboard` (2nd column = last exit code, 0 = fine) |
| Reload LaunchAgent | `launchctl bootout gui/$(id -u)/com.lopushokbot.ru-dashboard; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lopushokbot.ru-dashboard.plist` |
| Live site | https://lopushokbot.github.io/ru-portfolio-dashboard/ |

## How the daily run works

1. launchd starts `run.sh` at 08:00 Dubai, at login, and every hour. `run.sh` exits immediately unless it's 08:00–22:59 Dubai, today has no successful run yet, and fewer than 4 attempts were made today — so a sleeping/offline Mac catches up the same day.
2. It holds `caffeinate`, waits up to 10 min for MOEX + GitHub to resolve, then runs `node scripts/update.mjs` (~2–3 min).
3. `update.mjs` writes `data.json`; `run.sh` commits it to `main` and pushes. GitHub Pages (branch `main`, root) redeploys in ~1 min.
4. Exit code 3 from update.mjs = core data missing (MOEX prices or smart-lab) → retried next hour. Any single failed source keeps its previous values and shows "N data warnings" in the page header (hover to read them).

## If something goes wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
| Header: "T-Bank token expired" | Token revoked/expired (HTTP 401) | New **read-only** token in the T-Investments app → Settings → API tokens. `echo "TBANK_TOKEN=..." > ~/ru-portfolio-dashboard/.env && chmod 600 .env` |
| Header: "T-Bank API unavailable", TLS/certificate errors | T-Bank changed its certificate chain | Check: `echo \| openssl s_client -connect invest-public-api.tbank.ru:443 -showcerts 2>/dev/null \| grep -E "s:\|i:"`. If the root is still "Russian Trusted Root CA", re-download https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt into `certs/russian_trusted_root_ca.pem` (SHA-256 must start `D2:6D:2D:02` and end `CA:8E:CF:31`). |
| Run log ends with "Network not ready (20/20)" | No network for 10 min | Nothing — next hourly tick retries |
| `Failed: push` | GitHub auth / conflict | `cd ~/ru-portfolio-dashboard && git status && git pull --rebase && git push` |
| A holding disappears from the table | Its trailing or forward EPS turned negative (hidden rule) | Expected; listed under "Not shown", returns automatically |
| "Sources disagree" note on a stock | smart-lab vs T-Bank TTM EPS differ > 25% | Informational. Check the company's IFRS release if it looks wrong |
| All trailing EPS null | smart-lab HTML changed | Fix `smartlabLtm()` in `scripts/lib.mjs` — it reads the last ("LTM") cell of each row of the `simple-little-table` on `/q/<T>/f/q/MSFO/` |
| Forward column empty for everything | Consensus source changed/blocked | See `scripts/forward.mjs` header; previous forward EPS is kept (marked "kept from an earlier run" in the tooltip) |
| Price stale for one ticker | Ticker renamed / delisted on MOEX | Update `config.json` |

## Add / remove a holding or peer

1. Edit `config.json` → `holdings` (`t` = MOEX ticker, `group` = key in `groups`) or `peers`, and the group's `members`.
2. If smart-lab uses a different ticker, add it to `SL_TICKER` in `scripts/update.mjs`.
3. `node scripts/update.mjs`, check locally, commit + push.
4. Update CLAUDE.md holdings list + this log.

## Curated notes

`data.json → notes[]` survives every run: `{ "t": ["LKOH"], "title": "…", "text": "…", "until": "2027-03-31" }` — shown until `until`, with footnote markers on the listed tickers.

## Log

- **2026-10-20 (v3.1)** — Sema: SBER + T on P/B instead of P/E (bank P/B chart, P/B history bands, bank-median benchmark); everything grouped by sector (table headers with sector medians, sector-labelled charts and history).
- **2026-10-20 (v3)** — Rebuilt from scratch in the US-dashboard format at Sema's request (see CLAUDE.md). Fixed T-Bank (state-CA certificate), fixed "not updating" (daily run with catch-up + network wait + git identity), Pages moved from the force-pushed `gh-pages` branch to `main`. v2 Python code is in git history and at `~/ru-portfolio-dashboard-v2-backup/`.
