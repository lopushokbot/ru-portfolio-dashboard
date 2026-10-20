// Daily refresh: prices, earnings, dividends, report dates, analyst targets, index multiples → data.json.
// Usage: node scripts/update.mjs            (full run, ~3–4 min: smart-lab is fetched politely, ~1 req/s)
// Every source is optional: if one fails, the previous value in data.json is kept and flagged as stale.
import fs from "node:fs";
import path from "node:path";
import * as L from "./lib.mjs";
import { forwardEstimates } from "./forward.mjs";

const CFG = L.readJSON(path.join(L.ROOT, "config.json"));
const PREV = fs.existsSync(L.DATA_PATH) ? L.readJSON(L.DATA_PATH) : {};
const prevOf = t => [...(PREV.stocks || []), ...(PREV.peers || []), ...(PREV.universe || [])].find(s => s.t === t) || {};
const warnings = [];
const SL_TICKER = { /* smart-lab uses the company's common-share page for prefs */ SBERP: "SBER", TATNP: "TATN", SNGSP: "SNGS", TRNFP: "TRNFP" };
const slOf = t => SL_TICKER[t] || t;

/* ---------- 1. Universe: holdings + peers + every IMOEX constituent ---------- */
const ix = await L.moexIndex(CFG.index);
L.log(`${CFG.index} ${ix.level} on ${ix.date}, ${ix.members.length} members (weights ${ix.weightsDate})`);
const holdings = CFG.holdings.map(h => h.t), peers = CFG.peers.map(p => p.t);
const universe = [...new Set([...holdings, ...peers, ...ix.members.map(m => m.t)])];

/* ---------- 2. Prices: last official MOEX close ---------- */
const { closes, date: priceDate } = await L.moexCloses();
L.log(`MOEX closes: ${Object.keys(closes).length} securities, ${priceDate}`);

/* ---------- 3. smart-lab IFRS LTM (primary trailing EPS) ---------- */
const SL = {};
const slNeeded = [...new Set(universe.map(slOf))];
for (const t of slNeeded) {
  try { SL[t] = await L.smartlabLtm(t); }
  catch (e) { L.log(`  smart-lab ${t}: ${e.message}`); }
  await L.sleep(900);
}
L.log(`smart-lab LTM: ${Object.keys(SL).length}/${slNeeded.length}`);

/* ---------- 4. T-Bank: TTM cross-check, dividends, report dates, analyst consensus ---------- */
const TB = {};
const token = L.tbankToken();
let tbankOk = false;
if (!token) warnings.push("T-Bank token missing");
else {
  try {
    // per-ticker ShareBy (~0.2 s each); the bulk Shares list takes 80+ s since T-Bank's 2026 API changes
    const bySym = {};
    for (const t of universe) {
      try { bySym[t] = (await L.tb("InstrumentsService/ShareBy", { idType: "INSTRUMENT_ID_TYPE_TICKER", classCode: "TQBR", id: t }, token)).instrument; }
      catch (e) { if (e.status === 401) throw e; L.log(`  T-Bank instrument ${t}: ${e.message}`); }
    }
    const assets = [...new Set(universe.map(t => bySym[t]?.assetUid).filter(Boolean))];
    const fund = (await L.tb("InstrumentsService/GetAssetFundamentals", { assets }, token)).fundamentals;
    const fByAsset = Object.fromEntries(fund.map(f => [f.assetUid, f]));
    const now = new Date(), yearAgo = new Date(now - 365 * 864e5), yearAhead = new Date(+now + 400 * 864e5);
    for (const t of universe) {
      const s = bySym[t]; if (!s) continue;
      const f = fByAsset[s.assetUid] || {};
      const rec = { eps: f.epsTtm || null, netIncome: f.netIncomeTtm ? f.netIncomeTtm / 1e9 : null, pb: f.priceToBookTtm || null };
      // dividends: paid in the last 12 months (by record date) + declared/upcoming
      try {
        const d = (await L.tb("InstrumentsService/GetDividends", { instrumentId: s.uid, from: yearAgo.toISOString(), to: yearAhead.toISOString() }, token)).dividends || [];
        const val = x => L.q(x.dividendNet);
        const todayIso = now.toISOString().slice(0, 10);
        const past = d.filter(x => (x.recordDate || x.lastBuyDate || "").slice(0, 10) <= todayIso && (x.recordDate || "").slice(0, 10) >= yearAgo.toISOString().slice(0, 10));
        const next = d.filter(x => (x.recordDate || "").slice(0, 10) > todayIso).sort((a, b) => a.recordDate.localeCompare(b.recordDate))[0];
        rec.divTtm = past.reduce((a, x) => a + (val(x) || 0), 0) || 0;
        rec.divPast = past.map(x => ({ record: x.recordDate.slice(0, 10), amt: val(x) })).sort((a, b) => b.record.localeCompare(a.record));
        if (next) rec.nextDiv = { record: next.recordDate.slice(0, 10), lastBuy: (next.lastBuyDate || "").slice(0, 10) || null, amt: val(next) };
      } catch (e) { L.log(`  T-Bank dividends ${t}: ${e.message}`); }
      if (holdings.includes(t) || peers.includes(t)) {
        try {
          const ev = (await L.tb("InstrumentsService/GetAssetReports", { instrumentId: s.uid, from: new Date(now - 400 * 864e5).toISOString(), to: yearAhead.toISOString() }, token)).events || [];
          // T-Bank lists RAS and IFRS events; keep the latest-created entry per (year, period) — reschedules supersede.
          const byPeriod = {};
          for (const e of ev) { const k = `${e.periodYear}-${e.periodType}-${e.periodNum}`; if (!byPeriod[k] || e.createdAt > byPeriod[k].createdAt) byPeriod[k] = e; }
          const all = Object.values(byPeriod).map(e => ({ date: e.reportDate.slice(0, 10), period: periodLabel(e) })).sort((a, b) => a.date.localeCompare(b.date));
          const todayIso = now.toISOString().slice(0, 10);
          rec.nextReport = all.find(e => e.date >= todayIso) || null;
          if (rec.nextReport) rec.nextReport.confirmed = true;
          else {
            // no date announced yet: same report one year on (e.g. last November's Q3 → this November), marked as an estimate
            const yAgo = new Date(now - 365 * 864e5).toISOString().slice(0, 10);
            const ref = all.find(e => e.date >= yAgo);
            if (ref) {
              const d = new Date(Date.parse(ref.date) + 364 * 864e5); // same weekday a year later
              if (d.toISOString().slice(0, 10) >= todayIso) rec.nextReport = { date: d.toISOString().slice(0, 10), period: ref.period.replace(/\d{4}/, y => String(+y + 1)), confirmed: false };
            }
          }
          rec.lastReport = [...all].reverse().find(e => e.date < todayIso) || null;
        } catch (e) { L.log(`  T-Bank reports ${t}: ${e.message}`); }
        try {
          const c = await L.tb("InstrumentsService/GetForecastBy", { instrumentId: s.uid }, token);
          if (c.consensus) rec.target = {
            consensus: L.q(c.consensus.consensus), min: L.q(c.consensus.minTarget), max: L.q(c.consensus.maxTarget),
            rec: (c.consensus.recommendation || "").replace("RECOMMENDATION_", "").toLowerCase() || null,
            n: (c.targets || []).length || null,
          };
        } catch (e) { L.log(`  T-Bank consensus ${t}: ${e.message}`); }
      }
      TB[t] = rec;
      await L.sleep(120);
    }
    tbankOk = Object.keys(TB).length > universe.length * 0.8;
    L.log(`T-Bank: ${Object.keys(TB).length}/${universe.length} instruments`);
  } catch (e) {
    L.log(`T-Bank failed: ${e.message}`);
    warnings.push(e.status === 401 ? "T-Bank token expired — renew it in .env" : "T-Bank API unavailable");
  }
}
function periodLabel(e) {
  if (e.periodType === "PERIOD_TYPE_QUARTER") return `Q${e.periodNum} ${e.periodYear}`;
  if (e.periodType === "PERIOD_TYPE_SEMIANNUAL") return `H${e.periodNum} ${e.periodYear}`;
  if (e.periodType === "PERIOD_TYPE_ANNUAL") return `FY ${e.periodYear}`;
  return `${e.periodYear}`;
}

/* ---------- 4b. Company-announced IFRS report dates (smart-lab calendar) — beat T-Bank's estimates ---------- */
let CAL = [];
try { CAL = (await L.smartlabReportCalendar()).filter(x => /МСФО|IFRS|финансов/i.test(x.text)); L.log(`smart-lab calendar: ${CAL.length} IFRS events`); }
catch (e) { L.log(`smart-lab calendar: ${e.message}`); }
for (const t of [...holdings, ...peers]) {
  const hit = CAL.filter(x => new RegExp(`^${t}(:|\\s|$)`).test(x.text)).sort((a, b) => a.date.localeCompare(b.date))[0];
  if (!hit) continue;
  TB[t] = TB[t] || {};
  const cur = TB[t].nextReport;
  if (!cur || !cur.confirmed || hit.date < cur.date) {
    const per = /(\d)\s*кв/i.exec(hit.text) ? `Q${/(\d)\s*кв/i.exec(hit.text)[1]}` : /9\s*мес/i.test(hit.text) ? "9M" : /полугод|6\s*мес|1\s*п/i.test(hit.text) ? "H1" : /год/i.test(hit.text) ? "FY" : null;
    TB[t].nextReport = { date: hit.date, period: per ? `${per} ${hit.date.slice(0, 4)}` : (cur?.period ?? null), confirmed: !/предвар/i.test(hit.text) };
  }
}

// last resort for report dates: smart-lab's own report history one year on (semi-annual reporters such as LKOH, TATN)
for (const t of [...holdings, ...peers]) {
  if (TB[t]?.nextReport) continue;
  const today = L.todayDubai();
  const est = (SL[slOf(t)]?.reportDates || []).map(d => new Date(Date.parse(d) + 364 * 864e5).toISOString().slice(0, 10)).filter(d => d >= today).sort()[0];
  if (est) { TB[t] = TB[t] || {}; TB[t].nextReport = { date: est, period: null, confirmed: false }; }
}

/* ---------- 5. Forward estimates (dohod.ru next-12-months forecast) ---------- */
let FWD = {};
try { FWD = await forwardEstimates(universe, { closes, SL, prev: prevOf }); }
catch (e) { L.log(`Forward estimates failed: ${e.message}`); warnings.push("dohod.ru forecasts unavailable — forward EPS kept from the last run"); }
L.log(`Forward EPS: ${Object.values(FWD).filter(f => f && f.eps != null).length}/${universe.length}`);

/* ---------- 6. Assemble per-company records ---------- */
function build(t, meta = {}) {
  const prev = prevOf(t);
  const sl = SL[slOf(t)], tbr = TB[t] || {};
  const px = closes[t];
  const rec = { t, name: meta.name || prev.name || ix.members.find(m => m.t === t)?.name || t };
  if (meta.group) rec.group = meta.group;
  if (Object.values(CFG.groups).some(g => g.metric === "pb" && g.members.includes(t))) rec.metric = "pb";
  rec.price = px?.price ?? prev.price ?? null;
  rec.priceDate = px?.date ?? prev.priceDate ?? null;
  if (!px) warnings.push(`stale price ${t}`);

  // Trailing EPS: smart-lab IFRS LTM; T-Bank TTM as fallback + cross-check
  const slEps = sl?.eps ?? null, tbEps = tbr.eps ?? null;
  const tbSane = tbEps != null && rec.price && Math.abs(rec.price / tbEps) > 0.3; // T-Bank returns per-share junk for a few banks (e.g. 46,000 ₽)
  if (slEps != null && slEps !== 0) { rec.ttmEps = slEps; rec.ttmSrc = "smart-lab"; }
  else if (tbSane) { rec.ttmEps = tbEps; rec.ttmSrc = "T-Bank"; }
  else { rec.ttmEps = prev.ttmEps ?? null; rec.ttmSrc = prev.ttmSrc ?? null; }
  rec.ttmCheck = tbSane ? tbEps : null;

  rec.bvps = sl?.bvps ?? prev.bvps ?? null;
  const f = FWD[t];
  if (f && f.eps != null) Object.assign(rec, { fwdEps: f.eps, fwd: f });
  else if (prev.fwdEps != null) Object.assign(rec, { fwdEps: prev.fwdEps, fwd: { ...(prev.fwd || {}), stale: true } });
  else rec.fwdEps = null;

  // Dividends: T-Bank paid-in-last-12-months; smart-lab LTM as fallback
  const divTtm = tbankOk ? tbr.divTtm : null;
  rec.divTtm = divTtm ?? sl?.div ?? prev.divTtm ?? null;
  if (tbr.nextDiv) rec.nextDiv = tbr.nextDiv;
  if (tbr.divPast?.length) rec.divPast = tbr.divPast.slice(0, 4);

  if (holdings.includes(t) || peers.includes(t)) {
    rec.earnings = {
      lastReported: sl?.lastReported ?? prev.earnings?.lastReported ?? null,
      lastPeriod: tbr.lastReport?.period ?? prev.earnings?.lastPeriod ?? null,
      next: tbr.nextReport?.date ?? (prev.earnings?.next > L.todayDubai() ? prev.earnings.next : null),
      nextPeriod: tbr.nextReport?.period ?? null,
      nextConfirmed: tbr.nextReport?.confirmed ?? false,
      // a newer report already in smart-lab's table but not yet in its LTM numbers
      // smart-lab also opens a column for operating updates, so it only counts as a pending IFRS report
      // when no IFRS report is scheduled within the following 45 days
      pendingSince: (() => {
        const p = sl?.newestColumnDate && sl.lastReported && sl.newestColumnDate > sl.lastReported ? sl.newestColumnDate : null;
        const nx = tbr.nextReport?.date;
        return p && !(nx && (Date.parse(nx) - Date.parse(p)) / 864e5 < 45) ? p : null;
      })(),
    };
    rec.target = tbr.target ?? prev.target ?? null;
  }
  return rec;
}

const stocks = CFG.holdings.map(h => build(h.t, h));
const peerRecs = CFG.peers.map(p => build(p.t, p));
const universeRecs = universe.filter(t => !holdings.includes(t) && !peers.includes(t)).map(t => build(t));

/* ---------- 7. Own-history P/E bands (holdings, quarterly, last 5 years) ---------- */
const cutoff = `${new Date().getUTCFullYear() - 5}Q${Math.floor(new Date().getUTCMonth() / 3) + 1}`;
for (const s of stocks) {
  try {
    const pb = CFG.groups[s.group]?.metric === "pb";
    const h = (await L.smartlabPeHistory(slOf(s.t), pb ? "p_b" : "p_e")).filter(x => x.q >= cutoff);
    const ok = h.filter(x => x.pe > 0 && x.pe <= (pb ? 20 : 100));
    const vals = ok.map(x => x.pe).sort((a, b) => a - b);
    s.hist = vals.length ? {
      min: vals[0], max: vals.at(-1), median: L.median(vals), quarters: vals.length, excluded: h.length - ok.length,
      from: ok[0].q, to: ok.at(-1).q, source: "smart-lab", metric: pb ? "pb" : "pe",
    } : { quarters: 0 };
  } catch (e) { s.hist = prevOf(s.t).hist ?? null; L.log(`  history ${s.t}: ${e.message}`); }
  await L.sleep(900);
}

/* ---------- 8. Index multiples, bottom-up with index weights ----------
   P/E(index) = 1 ÷ Σ wᵢ·(EPSᵢ ÷ Priceᵢ): the free-float-weighted harmonic mean, i.e. Σ float cap ÷ Σ float earnings.
   Loss-makers included as negative earnings yield (index-provider convention); an ex-loss variant is stored too. */
const all = Object.fromEntries([...stocks, ...peerRecs, ...universeRecs].map(r => [r.t, r]));
function indexMultiple(key) {
  let wCov = 0, ey = 0, wPos = 0, eyPos = 0, losers = 0, n = 0;
  for (const m of ix.members) {
    const r = all[m.t]; const e = r?.[key];
    if (!r?.price || e == null) continue;
    n++; wCov += m.w; ey += m.w * (e / r.price);
    if (e > 0) { wPos += m.w; eyPos += m.w * (e / r.price); } else losers++;
  }
  if (!n || ey <= 0) return null;
  return { pe: wCov / ey, exLoss: eyPos > 0 ? wPos / eyPos : null, n, losers, coverage: wCov, level: ix.level, date: ix.date };
}
function indexYield() {
  let w = 0, y = 0, n = 0;
  for (const m of ix.members) { const r = all[m.t]; if (!r?.price || r.divTtm == null) continue; w += m.w; y += m.w * (r.divTtm / r.price); n++; }
  return n ? { pct: (y / w) * 100, n, coverage: w, date: ix.date } : null;
}
const prevIx = (PREV.indices || [])[0] || {};
const trailing = indexMultiple("ttmEps"), forward = indexMultiple("fwdEps"), dy = indexYield();
const keep = (fresh, old, min, label) => {
  if (fresh && fresh.coverage >= min) return fresh;
  if (old) { warnings.push(`${label} kept from ${old.date}`); return old; }
  return fresh;
};
const index = {
  key: CFG.index.toLowerCase(), name: "MOEX Russia Index", secid: CFG.index,
  price: ix.level, priceDate: ix.date, members: ix.members.length,
  trailing: keep(trailing, prevIx.trailing, 0.95, "Index trailing P/E"),
  forward: keep(forward, prevIx.forward, 0.85, "Index forward P/E"),
  divYield: keep(dy, prevIx.divYield, 0.9, "Index dividend yield"),
};
L.log(`IMOEX trailing ${index.trailing?.pe?.toFixed(2)}× (${index.trailing?.n}, cov ${(index.trailing?.coverage * 100).toFixed(1)}%) · forward ${index.forward?.pe?.toFixed(2)}× (cov ${(index.forward?.coverage * 100 || 0).toFixed(1)}%) · DY ${index.divYield?.pct?.toFixed(2)}%`);

/* ---------- 9. Macro: key rate, OFZ curve, USD/RUB ---------- */
const macro = { ...(PREV.macro || {}) };
try { macro.keyRate = await L.cbrKeyRate(); } catch (e) { L.log(`  CBR key rate: ${e.message}`); }
try { macro.ofz = await L.ofzCurve(); } catch (e) { L.log(`  OFZ curve: ${e.message}`); }
try { macro.usdrub = await L.cbrUsdRub(); } catch (e) { L.log(`  USD/RUB: ${e.message}`); }

/* ---------- 10. Write ---------- */
const out = {
  meta: {
    builtAt: new Date().toISOString(),
    pricesAsOf: priceDate,
    earningsAsOf: L.todayDubai(),
    forwardSource: "dohod.ru next-12-months net income forecast (Dohod's own analysts — not a multi-broker consensus)",
    sources: { smartlab: Object.keys(SL).length, tbank: Object.keys(TB).length, forward: Object.values(FWD).filter(f => f?.eps != null).length, universe: universe.length },
    warnings: [...new Set(warnings)].slice(0, 12),
  },
  indices: [index],
  macro,
  groups: CFG.groups,
  stocks,
  peers: peerRecs,
  universe: universeRecs.map(({ t, name, price, ttmEps, fwdEps, divTtm, ttmSrc }) => ({ t, name, price, ttmEps, fwdEps, divTtm, ttmSrc })),
  indexWeights: ix.members.map(m => ({ t: m.t, w: +m.w.toFixed(5) })),
  notes: PREV.notes || [],
};
L.writeJSON(L.DATA_PATH, out);
L.log(`data.json written · warnings: ${out.meta.warnings.length ? out.meta.warnings.join("; ") : "none"}`);
// exit non-zero only if the core failed (no prices or no earnings at all) so run.sh retries next hour
if (Object.keys(closes).length < 50 || Object.keys(SL).length < universe.length * 0.5) process.exit(3);
