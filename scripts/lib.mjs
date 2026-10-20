// Shared helpers: MOEX ISS (prices, index composition, OFZ curve), T-Bank Invest API (TTM cross-check,
// dividends, report dates, analyst targets), smart-lab.ru (IFRS LTM earnings, book value, P/E history).
// No Yahoo Finance anywhere — its Russian data has been wrong since 2022.
import fs from "node:fs";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const DATA_PATH = path.join(ROOT, "data.json");
export const sleep = ms => new Promise(r => setTimeout(r, ms));
export const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

export const readJSON = p => JSON.parse(fs.readFileSync(p, "utf8"));
export const writeJSON = (p, v) => fs.writeFileSync(p, JSON.stringify(v, null, 1) + "\n");
export const todayDubai = () => new Date(Date.now() + 4 * 3600e3).toISOString().slice(0, 10);

const BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36";

/* ---------------- generic HTTP with retries ---------------- */
export async function getText(url, { tries = 3, timeout = 30000, headers = {} } = {}) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": BROWSER_UA, ...headers }, signal: AbortSignal.timeout(timeout) });
      if (res.status === 404) throw Object.assign(new Error("HTTP 404"), { fatal: true });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.text();
    } catch (e) {
      last = e;
      if (e.fatal) break;
      await sleep(2000 * (i + 1));
    }
  }
  throw last;
}
export const getJSON = async (url, o) => JSON.parse(await getText(url, o));

/* ---------------- MOEX ISS ---------------- */
const ISS = "https://iss.moex.com/iss";
const table = (j, k) => (j[k]?.data || []).map(r => Object.fromEntries(j[k].columns.map((c, i) => [c, r[i]])));

/** Latest completed main-session official close for every TQBR share (one paginated call). */
export async function moexCloses() {
  const out = {};
  let start = 0, total = 1, date = null;
  while (start < total) {
    const j = await getJSON(`${ISS}/history/engines/stock/markets/shares/boards/TQBR/securities.json?iss.meta=off&start=${start}&history.columns=TRADEDATE,SECID,LEGALCLOSEPRICE,CLOSE,NUMTRADES`);
    const rows = table(j, "history");
    const cur = table(j, "history.cursor")[0];
    total = cur.TOTAL; start += cur.PAGESIZE;
    for (const r of rows) {
      const px = r.LEGALCLOSEPRICE || r.CLOSE;
      if (px > 0) out[r.SECID] = { price: px, date: r.TRADEDATE };
      date = r.TRADEDATE;
    }
  }
  return { closes: out, date };
}

/** Index close history (last ~10 sessions) + composition with weights (free-float cap weights, %). */
export async function moexIndex(secid) {
  const from = new Date(Date.now() - 20 * 864e5).toISOString().slice(0, 10);
  const h = table(await getJSON(`${ISS}/history/engines/stock/markets/index/securities/${secid}.json?iss.meta=off&from=${from}&history.columns=TRADEDATE,CLOSE`), "history");
  const last = h.filter(r => r.CLOSE > 0).at(-1);
  let comp = [], start = 0, total = 1;
  while (start < total) {
    const j = await getJSON(`${ISS}/statistics/engines/stock/markets/index/analytics/${secid}.json?iss.meta=off&limit=100&start=${start}`);
    comp.push(...table(j, "analytics"));
    const cur = table(j, "analytics.cursor")[0];
    total = cur ? cur.TOTAL : 0; start += cur ? cur.PAGESIZE : 1;
  }
  return {
    level: last?.CLOSE, date: last?.TRADEDATE,
    members: comp.map(r => ({ t: r.secids || r.ticker, w: r.weight / 100, name: r.shortnames })),
    weightsDate: comp[0]?.tradedate,
  };
}

/** OFZ zero-coupon yield curve (MOEX G-curve) — returns {date, y1, y5, y10}. */
export async function ofzCurve() {
  const rows = table(await getJSON(`${ISS}/engines/stock/zcyc.json?iss.meta=off&iss.only=yearyields`), "yearyields");
  const at = p => rows.find(r => Math.abs(r.period - p) < 1e-6)?.value ?? null;
  return { date: rows[0]?.tradedate, y1: at(1), y5: at(5), y10: at(10) };
}

/* ---------------- CBR ---------------- */
export async function cbrKeyRate() {
  const html = await getText("https://www.cbr.ru/hd_base/keyrate/");
  const m = [...html.matchAll(/<td>(\d{2}\.\d{2}\.\d{4})<\/td>\s*<td>([\d,]+)<\/td>/g)];
  if (!m.length) return null;
  const [d, v] = [m[0][1], m[0][2]];
  return { rate: parseFloat(v.replace(",", ".")), date: d.split(".").reverse().join("-") };
}
export async function cbrUsdRub() {
  const j = await getJSON("https://www.cbr-xml-daily.ru/daily_json.js");
  return { rate: j.Valute.USD.Value, date: j.Date.slice(0, 10) };
}

/* ---------------- T-Bank Invest API ----------------
   Since 2026 T-Bank serves its API with a certificate issued by the Russian state CA (Минцифры
   "Russian Trusted Root CA"), which no OS or Node trusts by default — every call failed TLS and the
   old dashboard got 0/20. We trust that root for T-Bank requests ONLY (pinned file in certs/). */
const TB_CA = fs.readFileSync(path.join(ROOT, "certs/russian_trusted_root_ca.pem"));
const TB_HOST = "invest-public-api.tbank.ru";
export function tbankToken() {
  if (process.env.TBANK_TOKEN) return process.env.TBANK_TOKEN;
  try { return fs.readFileSync(path.join(ROOT, ".env"), "utf8").match(/TBANK_TOKEN=(\S+)/)?.[1] || null; } catch { return null; }
}
function tbPost(method, body, token) {
  return new Promise((resolve, reject) => {
    let done = false;
    const ok = v => { if (!done) { done = true; clearTimeout(hard); resolve(v); } };
    const fail = e => { if (!done) { done = true; clearTimeout(hard); reject(e); } };
    // hard deadline: a socket that closes without 'end' must never leave the promise hanging
    const hard = setTimeout(() => { req.destroy(); fail(new Error("T-Bank deadline")); }, 45000);
    const req = https.request({
      host: TB_HOST, path: `/rest/tinkoff.public.invest.api.contract.v1.${method}`, method: "POST", ca: TB_CA, timeout: 30000,
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/json" },
    }, res => {
      let d = ""; res.setEncoding("utf8"); res.on("data", c => (d += c));
      res.on("error", fail);
      res.on("aborted", () => fail(new Error("T-Bank response aborted")));
      res.on("end", () => {
        if (res.statusCode !== 200) return fail(Object.assign(new Error(`T-Bank HTTP ${res.statusCode}`), { status: res.statusCode }));
        try { ok(JSON.parse(d)); } catch { fail(new Error("T-Bank bad JSON")); }
      });
      res.on("close", () => fail(new Error("T-Bank connection closed")));
    });
    req.on("error", fail);
    req.on("timeout", () => req.destroy(new Error("T-Bank timeout")));
    req.on("close", () => setTimeout(() => fail(new Error("T-Bank connection closed")), 0));
    req.end(JSON.stringify(body));
  });
}
export async function tb(method, body, token, tries = 3) {
  let last;
  for (let i = 0; i < tries; i++) {
    try { return await tbPost(method, body, token); }
    catch (e) { last = e; if (e.status === 401 || e.status === 403) break; await sleep(1500 * (i + 1)); }
  }
  throw last;
}
export const q = m => (m ? Number(m.units || 0) + Number(m.nano || 0) / 1e9 : null);

/* ---------------- smart-lab.ru ---------------- */
const num = s => {
  if (s == null) return null;
  const t = String(s).replace(/ /g, "").replace(/\s/g, "").replace(",", ".").replace("%", "");
  if (!t || t === "—" || t === "-") return null;
  const v = parseFloat(t);
  return Number.isFinite(v) ? v : null;
};
const strip = h => h.replace(/<[^>]+>/g, " ").replace(/&nbsp;/g, " ").replace(/\s+/g, " ").trim();
const ruDate = s => { const m = /(\d{2})\.(\d{2})\.(\d{4})/.exec(s || ""); return m ? `${m[3]}-${m[2]}-${m[1]}` : null; };

/** IFRS quarterly table → LTM column: EPS, net income, equity, shares, dividend, last report date.
 *  Works for quarterly and half-year reporters alike (smart-lab's LTM column already sums the right periods). */
export async function smartlabLtm(slTicker) {
  const html = await getText(`https://smart-lab.ru/q/${slTicker}/f/q/MSFO/`);
  const tbl = /<table[^>]*simple-little-table[^>]*>([\s\S]*?)<\/table>/.exec(html);
  if (!tbl) throw new Error("no table");
  const rows = {};
  let header = null;
  for (const tr of tbl[1].split(/<tr/i).slice(1)) {
    const cells = [...tr.matchAll(/<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi)].map(m => strip(m[1]));
    if (!cells.length) continue;
    const label = cells[0].replace(/\s*,.*$/, "").trim();
    if (!header && /LTM/.test(cells.join(" "))) header = cells;
    if (label && !(label in rows)) rows[label] = cells;
  }
  const ltm = label => { const c = rows[label]; return c ? num(c.at(-1)) : null; };
  const series = label => { const c = rows[label]; return c ? c.slice(3, -2).map(num) : []; };
  const dates = rows["Дата отчета"] ? rows["Дата отчета"].slice(3).map(ruDate) : [];
  const shares = (ltm("Число акций ао") || 0) + (ltm("Число акций ап") || 0);
  const equity = ltm("Капитал") ?? ltm("Собственный капитал") ?? ltm("Балансовая стоимость");
  return {
    eps: ltm("EPS"),
    netIncome: ltm("Чистая прибыль"),
    currency: rows["Валюта отчета"]?.at(-1) || "RUB",
    equity, shares: shares || null,
    bvps: equity && shares ? (equity * 1e9) / (shares * 1e6) : null,
    pb: ltm("P/B") ?? ltm("P/BV"),
    pe: ltm("P/E"),
    div: ltm("Дивиденд"),
    lastReported: dates.filter(Boolean).at(-1) || null,
    // the newest report column can be published before smart-lab fills its numbers in
    newestColumnDate: dates.slice(0, -2).filter(Boolean).at(-1) || null,
    newestColumnEps: series("EPS").at(-1),
    periods: header ? header.slice(3, -2).filter(Boolean) : [],
    reportDates: [...new Set(dates.filter(Boolean))].sort(),
  };
}

/** smart-lab company-reports calendar: [{date, text}] for the next ~5 months (company-announced dates). */
export async function smartlabReportCalendar() {
  const d = n => { const x = new Date(Date.now() + n * 864e5); return `${String(x.getUTCDate()).padStart(2, "0")}.${String(x.getUTCMonth() + 1).padStart(2, "0")}.${x.getUTCFullYear()}`; };
  const base = `https://smart-lab.ru/calendar/stocks/company_reports/country_0/from_${d(0)}/to_${d(160)}/`;
  const out = [];
  for (let page = 1; page <= 6; page++) {
    let html;
    try { html = await getText(page === 1 ? base : `${base}page${page}/`, { tries: 2 }); } catch { break; }
    const tbl = /<table[^>]*simple-little-table[^>]*>([\s\S]*?)<\/table>/.exec(html);
    if (!tbl) break;
    let n = 0;
    for (const tr of tbl[1].split(/<tr/i).slice(1)) {
      const cells = [...tr.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map(m => strip(m[1]));
      const date = ruDate(cells[0]);
      const text = cells.slice(1).filter(Boolean).find(c => c.length > 6 && c !== ">>>");
      if (date && text) { out.push({ date, text }); n++; }
    }
    if (n < 20) break;
    await sleep(800);
  }
  return out;
}

/** Quarterly trailing P/E history (smart-lab chart data, back to ~2014). */
export async function smartlabPeHistory(slTicker) {
  const html = await getText(`https://smart-lab.ru/q/${slTicker}/MSFO/p_e/`);
  const m = /var aQuarterData = \{\s*'diagram' : (\{[\s\S]*?\}),\s*\n\s*'change_diagram'/.exec(html);
  if (!m) return [];
  const d = JSON.parse(m[1]);
  return d.categories.map((c, i) => ({ q: c, pe: d.data[i]?.y ?? null })).filter(x => x.q !== "LTM");
}

export const pctChange = (a, b) => (a != null && b ? a / b - 1 : null);
export const median = a => {
  const v = a.filter(x => x != null && Number.isFinite(x)).sort((p, q) => p - q);
  if (!v.length) return null;
  const h = v.length >> 1;
  return v.length % 2 ? v[h] : (v[h - 1] + v[h]) / 2;
};
