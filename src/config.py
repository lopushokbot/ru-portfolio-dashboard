"""
Configuration for Russian Portfolio Dashboard v2.
Tickers, names, sectors, mappings, thresholds.
"""

PORTFOLIO = ["YDEX", "TCSG", "LKOH", "HEAD", "SBER", "X5", "NVTK", "GMKN", "CNRU", "TATN"]

TICKER_NAMES = {
    "YDEX": "Яндекс",
    "TCSG": "Т-Технологии",
    "LKOH": "ЛУКОЙЛ",
    "HEAD": "HeadHunter",
    "SBER": "Сбербанк",
    "X5":   "X5 Group",
    "NVTK": "НОВАТЭК",
    "GMKN": "Норильский никель",
    "CNRU": "ЦИАН",
    "TATN": "Татнефть",
    "ROSN": "Роснефть",
    "GAZP": "Газпром",
    "VTBR": "ВТБ",
    "BSPB": "Банк СПБ",
    "NLMK": "НЛМК",
    "MAGN": "ММК",
    "CHMF": "Северсталь",
    "MGNT": "Магнит",
    "OZON": "Ozon",
    "VK":   "VK",
}

SECTORS = [
    {
        "name": "🛢️ Oil & Gas",
        "tickers": ["LKOH", "ROSN", "NVTK", "TATN", "GAZP"],
        "portfolio": ["LKOH", "NVTK", "TATN"],
        "is_bank": False,
    },
    {
        "name": "🏦 Banks / Fintech",
        "tickers": ["SBER", "VTBR", "TCSG", "BSPB"],
        "portfolio": ["SBER", "TCSG"],
        "is_bank": True,
    },
    {
        "name": "⛏️ Metals & Mining",
        "tickers": ["GMKN", "NLMK", "MAGN", "CHMF"],
        "portfolio": ["GMKN"],
        "is_bank": False,
    },
    {
        "name": "🛒 Retail",
        "tickers": ["X5", "MGNT", "OZON"],
        "portfolio": ["X5"],
        "is_bank": False,
    },
    {
        "name": "💻 Tech / Internet",
        "tickers": ["YDEX", "HEAD", "CNRU", "VK"],
        "portfolio": ["YDEX", "HEAD", "CNRU"],
        "is_bank": False,
    },
]

BANKS = {"SBER", "TCSG", "VTBR", "BSPB"}

# ── Ticker mappings ──────────────────────────────────────────────────────────

MOEX_TICKER = {
    "TCSG": "T",
    "VK":   "VKCO",
}

SMARTLAB_TICKER = {
    "TCSG": "T",
    "X5":   "X5",
    "BSPB": "BSPB",
    "VK":   "VKCO",
}

YAHOO_TICKER = {
    "TCSG": "TCSG.ME",
    "X5":   "X5.ME",
    "YDEX": "YDEX.ME",
    "LKOH": "LKOH.ME",
    "HEAD": "HEAD.ME",
    "SBER": "SBER.ME",
    "NVTK": "NVTK.ME",
    "GMKN": "GMKN.ME",
    "CNRU": "CNRU.ME",
    "TATN": "TATN.ME",
    "ROSN": "ROSN.ME",
    "GAZP": "GAZP.ME",
    "VTBR": "VTBR.ME",
    "BSPB": "BSPB.ME",
    "NLMK": "NLMK.ME",
    "MAGN": "MAGN.ME",
    "CHMF": "CHMF.ME",
    "MGNT": "MGNT.ME",
    "OZON": "OZON.ME",     # may not be available on Yahoo
    "VK":   "VKCO.ME",     # may not be available on Yahoo
}

FINRANGE_TICKER = {
    "TCSG": "T",
    "VK":   "VKCO",
}

# ── Validation thresholds ────────────────────────────────────────────────────

THRESHOLDS = {
    "ratio":      0.35,   # P/E, EV/EBITDA, P/B, P/S — 35% relative (TTM vs annual differ)
    "percentage":  15.0,   # margins, ROE, yields — 15pp absolute (methodology gaps)
    "absolute":   0.30,   # revenue, debt in ₽B — 30% relative (TTM vs fiscal year)
}

RATIO_METRICS = {"pe", "ev_ebitda", "pbv", "ps", "nd_ebitda", "debt_to_equity"}
PCT_METRICS = {"net_margin", "roe", "div_yield", "rev_yoy", "ebitda_yoy", "ni_yoy", "change_pct",
               "div_payout_ratio", "rev_3y_cagr", "free_float", "beta"}
ABS_METRICS = {"revenue_b", "ebitda_b", "net_income_b", "net_debt_b", "mktcap",
               "total_debt_b", "fcf_b", "ev_b"}

# ── Network ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

MOEX_BASE = "https://iss.moex.com/iss"
SMARTLAB_BASE = "https://smart-lab.ru/q"
