// Forward (next-twelve-months) earnings.
//
// Source: dohod.ru — "Прогноз прибыли в след. 12m" on https://www.dohod.ru/ik/analytics/dividend/<ticker>.
// This is Dohod's own analyst forecast of net income over the next 12 months (a house view, not a multi-broker
// consensus). Researched 2026-10-20: no free machine-readable consensus exists for MOEX stocks — smart-lab,
// MarketScreener, investing.com, TradingView, BCS, Finam, conomy all either lack forecasts or gate them. The only true
// consensus (median of brokers, FY2026E/FY2027E) is Cbonds (cbonds.ru, paid API) — swap it in here if subscribed.
//
// Forward EPS = forecast net income ÷ the share count implied by smart-lab's own trailing EPS (net income ÷ EPS),
// so trailing and forward multiples divide by the same share base (dohod counts SBER ordinary shares only, for example).
import * as L from "./lib.mjs";

const num = s => { const v = parseFloat(String(s).replace(/\s|\u00a0/g, "").replace(",", ".")); return Number.isFinite(v) ? v : null; };

export async function dohodForecast(t) {
  const html = await L.getText(`https://www.dohod.ru/ik/analytics/dividend/${t.toLowerCase()}`, { tries: 2 });
  const ni = /Прогноз прибыли в след\. 12m:\s*<strong><span[^>]*>([-\d.,\s]+)<\/span>\s*млн/i.exec(html);
  const sh = /Количество акций в обращении:\s*<strong><span[^>]*>([\d.,\s]+)<\/span>\s*млн/i.exec(html);
  const niM = ni ? num(ni[1]) : null, shM = sh ? num(sh[1]) : null;
  if (niM == null || niM === 0) return null; // 0 = no forecast published (e.g. Magnit)
  return { netIncome: niM / 1e3, shares: shM, eps: shM ? niM / shM : null };
}

/** Returns { [ticker]: { eps, netIncome, source, basis } } for every ticker dohod covers. */
export async function forwardEstimates(tickers, { SL = {} } = {}) {
  const out = {};
  const SL_OF = { SBERP: "SBER", TATNP: "TATN", SNGSP: "SNGS" };
  for (const t of tickers) {
    try {
      const f = await dohodForecast(t);
      if (f) {
        const sl = SL[SL_OF[t] || t];
        const slShares = sl && sl.eps > 0 && sl.netIncome > 0 ? (sl.netIncome * 1e3) / sl.eps : null; // million shares
        const eps = slShares ? (f.netIncome * 1e3) / slShares : f.eps;
        out[t] = { eps, netIncome: f.netIncome, source: "dohod.ru", basis: "ntm" };
      }
    } catch (e) {
      if (!/404/.test(e.message)) L.log(`  dohod ${t}: ${e.message}`);
    }
    await L.sleep(500);
  }
  return out;
}
