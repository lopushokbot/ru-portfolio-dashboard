# Russian Portfolio Valuation Dashboard (v3)

Apple-style static dashboard of trailing and forward P/E for Sema's 10 Russian holdings versus hand-picked peer groups and a bottom-up MOEX Russia Index, plus dividend yields, analyst target prices, report/dividend calendar and the equity–OFZ yield gap. Same format and design system as the US Portfolio Valuation Dashboard (`~/Documents/ppppp/workspace/us-portfolio-dashboard`). Static `index.html` + `data.json`, no build step.

## Live / paths

| | |
|---|---|
| Live | https://lopushokbot.github.io/ru-portfolio-dashboard/ (GitHub Pages, branch `main`, root) |
| GitHub | https://github.com/lopushokbot/ru-portfolio-dashboard (public — data.json holds only public market data) |
| Local (canonical) | `/Users/iibot/ru-portfolio-dashboard/` — outside `~/Documents` because macOS TCC blocks launchd there. Symlink at `~/Documents/ppppp/workspace/ru-portfolio-dashboard`. |
| Schedule | LaunchAgent `com.lopushokbot.ru-dashboard` (plist copy in repo) → `run.sh`: daily 08:00 Dubai + hourly catch-up until 22:59, one success/day |
| v2 backup | `~/ru-portfolio-dashboard-v2-backup/` (old Python 5-source generator, incl. its uncommitted local edits) |

## Why it runs locally, not in GitHub Actions

The T-Bank (T-Investments) token must never leave the Mac (`.env`, chmod 600, gitignored). Russian sites may also block foreign CI IPs.

## Files

```
index.html          — the page (CSS + JS); fetches data.json, derives every ratio client-side
data.json           — written by scripts/update.mjs; notes[] is the only hand-edited part
config.json         — holdings, peers, peer groups (edit here)
scripts/lib.mjs      — MOEX ISS, CBR, T-Bank (scoped CA), smart-lab parsers
scripts/update.mjs   — daily orchestrator (~3 min)
scripts/forward.mjs  — forward EPS (dohod.ru); the place to plug in a paid consensus (Cbonds)
certs/russian_trusted_root_ca.pem — Минцифры root, trusted for T-Bank requests ONLY
run.sh              — LaunchAgent wrapper (guards, caffeinate, network wait, commit + push)
assets/fonts/       — New York Large + Inter, bundled
```

## Data sources (no Yahoo — wrong for Russian stocks since 2022)

| Data | Source | Notes |
|---|---|---|
| Prices | MOEX ISS history, TQBR `LEGALCLOSEPRICE` | last completed main session |
| Index level, composition, weights | MOEX ISS `statistics/.../analytics/IMOEX` | 44 members |
| Trailing EPS (primary) | smart-lab.ru `/q/<T>/f/q/MSFO/` LTM column | IFRS; handles half-year reporters (LKOH, NVTK, TATN, GMKN) |
| Trailing EPS (cross-check) | T-Bank `GetAssetFundamentals.epsTtm` | per-share junk for some banks (BSPB/VTBR ≈ 46,000 ₽) — sanity-filtered; >25% gaps auto-flagged in Notes |
| Forward EPS | dohod.ru "Прогноз прибыли в след. 12m" | Dohod's house forecast, NOT a consensus; ÷ smart-lab share base. No free consensus exists (researched 2026-10-20); Cbonds is the paid consensus |
| Dividends | T-Bank `GetDividends` | TTM by record date + next declared |
| Report dates | smart-lab calendar → T-Bank `GetAssetReports` → last year + 364 d (est.) | |
| Analyst target | T-Bank `GetForecastBy` consensus | |
| P/E history | smart-lab `/q/<T>/MSFO/p_e/` embedded chart data | quarterly since 2014 |
| Key rate / USD/RUB / OFZ curve | cbr.ru, cbr-xml-daily, MOEX zcyc | |

## T-Bank API gotcha (the "T-Bank not working" bug, fixed 2026-10-20)

T-Bank serves `invest-public-api.tbank.ru` (and the old tinkoff.ru host) with a certificate from the Russian state CA ("Russian Trusted Root CA", Минцифры). No OS/Python/Node trusts it, so every call failed TLS and retried into timeouts (runs took 30+ min, 0/20 fundamentals since ~Oct 2026). Fix: the pinned root in `certs/`, passed as `ca` to T-Bank requests only. Also: the bulk `Shares` list takes 80+ s — use per-ticker `ShareBy`.

## Methodology (keep consistent)

- Trailing P/E = MOEX close ÷ smart-lab IFRS LTM EPS. Forward P/E = close ÷ dohod NTM EPS.
- Index P/E = 1 ÷ Σ wᵢ·EPSᵢ/Pᵢ over IMOEX members at published weights (= Σ float cap ÷ Σ float earnings); loss-makers included, ex-loss also shown; ordinary + preferred classes each weighted with the same company EPS. Kept from the previous run if coverage < 95% (trailing) / 85% (forward).
- Peer benchmark = median of members' positive multiples (mean shown too). Groups: banks, oil & gas, metals, food retail, internet (config.json).
- Hidden rule (as US): holdings with negative trailing or forward EPS are hidden and listed under the table; they return automatically.
- Banks on P/E (Russian convention), P/B in Notes.
- Index trailing ≈ 4× is genuine: GAZP + SNGS (FX revaluation) ≈ 40% of index earnings — explained in Notes.

## Rules

- Never commit `.env`; never send the token anywhere but T-Bank.
- Don't hardcode numbers in index.html — everything comes from data.json.
- Weekly Claude review routine "Russian Portfolio Dashboard Review" (Sundays) checks the live page — keep its prompt in sync if the structure changes.
- Update RUNBOOK.md log after changes.
