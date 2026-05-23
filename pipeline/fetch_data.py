"""
fetch_data.py
Fetches market data (previous day closing prices), macro news, sector news,
Serbian financial news, winners/losers, VIX, yields, sentiment, market clock.
EUR/RSD pulled directly from NBS XML feed.
"""

import os
import json
import datetime
import feedparser
import yfinance as yf
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Config ─────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
OUTPUT_DIR   = Path(__file__).parent.parent / "docs" / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CET       = ZoneInfo("Europe/Belgrade")
TODAY     = datetime.datetime.now(CET).date()
TODAY_STR = TODAY.isoformat()

# ── Tickers ─────────────────────────────────────────────────────────────────
TICKERS = {
    "indices": {
        "S&P 500":       "^GSPC",
        "NASDAQ":        "^IXIC",
        "Dow Jones":     "^DJI",
        "DAX":           "^GDAXI",
        "Euro Stoxx 50": "^STOXX50E",
        "FTSE 100":      "^FTSE",
        "CAC 40":        "^FCHI",
        "Nikkei 225":    "^N225",
    },
    "sectors": {
        "Financials":    "XLF",
        "Energy":        "XLE",
        "Technology":    "XLK",
        "Healthcare":    "XLV",
        "Industrials":   "XLI",
        "Consumer Disc": "XLY",
        "Materials":     "XLB",
        "Utilities":     "XLU",
        "Real Estate":   "XLRE",
        "Comm Services": "XLC",
        "Consumer Stap": "XLP",
    },
    "fx_commodities": {
        "EUR/USD":    "EURUSD=X",
        "GBP/USD":    "GBPUSD=X",
        "USD/CHF":    "USDCHF=X",
        "USD/JPY":    "USDJPY=X",
        "Gold":       "GC=F",
        "Silver":     "SI=F",
        "Brent Crude":"BZ=F",
        "WTI Crude":  "CL=F",
        "Natural Gas":"NG=F",
        "Copper":     "HG=F",
        "Wheat":      "ZW=F",
    },
    "rates": {
        "VIX":          "^VIX",
        "US 10Y Yield": "^TNX",
        "US 2Y Yield":  "^IRX",
        "US 30Y Yield": "^TYX",
    },
    "large_cap": {
        "Apple":          "AAPL",
        "Microsoft":      "MSFT",
        "Alphabet":       "GOOGL",
        "Amazon":         "AMZN",
        "NVIDIA":         "NVDA",
        "Meta":           "META",
        "Tesla":          "TSLA",
        "JPMorgan":       "JPM",
        "Goldman Sachs":  "GS",
        "ExxonMobil":     "XOM",
        "Berkshire B":    "BRK-B",
        "Visa":           "V",
        "Johnson&Johnson":"JNJ",
        "UnitedHealth":   "UNH",
        "Procter&Gamble": "PG",
    }
}

# S&P 500 sample for winners/losers
SP500_SAMPLE = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","BRK-B","JPM","V",
    "UNH","XOM","JNJ","PG","MA","HD","CVX","MRK","ABBV","PEP",
    "KO","AVGO","COST","TMO","MCD","ACN","LIN","DHR","TXN","NEE",
    "PM","UPS","MS","LOW","INTC","INTU","QCOM","AMD","SBUX","AXP",
    "GE","CAT","BA","GS","BLK","SPGI","ISRG","GILD","MDLZ","C",
    "WFC","USB","PLD","AMT","CCI","DUK","SO","AEP","EXC","SRE",
    "F","GM","UBER","LYFT","ABNB","SNOW","PLTR","COIN","PYPL",
]

# ── RSS Feeds ────────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "macro_global": [
        ("Reuters Business",  "https://feeds.reuters.com/reuters/businessNews"),
        ("FT Markets",        "https://www.ft.com/rss/home/uk"),
        ("ECB Press",         "https://www.ecb.europa.eu/rss/press.html"),
        ("IMF News",          "https://www.imf.org/en/News/rss?language=eng"),
        ("WSJ Markets",       "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ],
    "serbia": [
        ("NBS",               "https://www.nbs.rs/internet/latinica/scripts/rss.html"),
        ("N1 Ekonomija",      "https://n1info.rs/feed/"),
        ("Novosti Ekonomija", "https://www.novosti.rs/rss/ekonomija.xml"),
        ("Telegraf Biznis",   "https://www.telegraf.rs/rss/biznis"),
        ("Danas Ekonomija",   "https://www.danas.rs/ekonomija/feed/"),
        ("Euronews Serbia",   "https://rs.euronews.com/rss"),
        ("Nova Ekonomija",    "https://novaekonomija.rs/feed"),
    ]
}

# ── NBS Exchange Rates ────────────────────────────────────────────────────────
def fetch_nbs_rates():
    result = {}
    try:
        from bs4 import BeautifulSoup
        url = "https://webappcenter.nbs.rs/ExchangeRateWebApp/ExchangeRate/CurrentMiddleRate"
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        currency_map = {"EUR": "EUR/RSD", "USD": "USD/RSD", "GBP": "GBP/RSD", "CHF": "CHF/RSD"}
        rate_date = TODAY_STR

        for row in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if cells and cells[0] in currency_map:
                price = float(cells[4].replace(",", "."))
                result[currency_map[cells[0]]] = {
                    "symbol":    cells[0] + "RSD",
                    "price":     round(price, 4),
                    "change_pct": None,
                    "source":    "NBS official",
                    "rate_date": rate_date
                }
    except Exception as e:
        print(f"NBS scrape failed: {e}")

    # Day-over-day change from yesterday's saved data
    try:
        yest_path = OUTPUT_DIR / f"daily_{(TODAY - datetime.timedelta(days=1)).isoformat()}.json"
        if yest_path.exists():
            with open(yest_path) as f:
                yest = json.load(f)
            for key, val in result.items():
                prev = yest.get("nbs_rates", {}).get(key, {}).get("price")
                if prev:
                    val["change_pct"] = round((val["price"] - prev) / prev * 100, 4)
                    val["prev_close"] = prev
    except Exception:
        pass

    return result


# ── Market Data (closing prices) ─────────────────────────────────────────────
def fetch_ticker_batch(symbols, period="5d"):
    """Always use period=5d to ensure we get last completed trading day close."""
    try:
        data = yf.download(symbols, period=period, interval="1d",
                           progress=False, auto_adjust=True)
        if len(symbols) == 1:
            closes = data["Close"].to_frame(symbols[0])
        else:
            closes = data["Close"]
        return closes
    except Exception:
        return None


def price_row(closes, symbol):
    """Extract last two closing prices and compute change."""
    try:
        if symbol not in closes.columns:
            return None
        prices = closes[symbol].dropna()
        if len(prices) >= 2:
            prev = float(prices.iloc[-2])
            curr = float(prices.iloc[-1])
            pct  = (curr - prev) / prev * 100
            return {
                "symbol":     symbol,
                "price":      round(curr, 4),
                "change_pct": round(pct, 2),
                "prev_close": round(prev, 4)
            }
        elif len(prices) == 1:
            return {
                "symbol":     symbol,
                "price":      round(float(prices.iloc[-1]), 4),
                "change_pct": None,
                "prev_close": None
            }
    except Exception:
        return None
    return None


def fetch_market_data():
    result = {}
    all_tickers = {}
    for category, tickers in TICKERS.items():
        all_tickers.update(tickers)

    closes = fetch_ticker_batch(list(all_tickers.values()))
    if closes is None:
        return {"error": "yfinance download failed"}

    for category, tickers in TICKERS.items():
        result[category] = {}
        for name, symbol in tickers.items():
            row = price_row(closes, symbol)
            result[category][name] = row if row else {
                "symbol": symbol, "price": None, "change_pct": None
            }

    # 2s10s yield curve spread
    try:
        t10 = result.get("rates", {}).get("US 10Y Yield", {}).get("price")
        t2  = result.get("rates", {}).get("US 2Y Yield",  {}).get("price")
        if t10 and t2:
            spread = round(t10 - t2, 3)
            result["rates"]["2s10s Spread"] = {
                "symbol":     "SPREAD",
                "price":      spread,
                "change_pct": None,
                "note":       "positive = normal curve, negative = inverted (recession signal)"
            }
    except Exception:
        pass

    return result


def fetch_winners_losers():
    try:
        closes = fetch_ticker_batch(SP500_SAMPLE)
        if closes is None:
            return {"winners": [], "losers": []}

        movers = []
        for symbol in SP500_SAMPLE:
            row = price_row(closes, symbol)
            if row and row.get("change_pct") is not None:
                movers.append({
                    "name":       symbol,
                    "symbol":     symbol,
                    "price":      row["price"],
                    "change_pct": row["change_pct"]
                })

        movers.sort(key=lambda x: x["change_pct"], reverse=True)
        return {"winners": movers[:10], "losers": movers[-10:][::-1]}
    except Exception as e:
        return {"winners": [], "losers": [], "error": str(e)}


# ── Sentiment scoring ─────────────────────────────────────────────────────────
POSITIVE_WORDS = {
    "rise","rises","rose","gain","gains","gained","surge","surges","surged",
    "rally","rallies","rallied","beat","beats","strong","stronger","growth",
    "record","high","profit","profits","bullish","up","positive","recovery"
}
NEGATIVE_WORDS = {
    "fall","falls","fell","drop","drops","dropped","plunge","plunges","plunged",
    "decline","declines","declined","miss","misses","weak","weaker","loss","losses",
    "recession","crisis","bearish","down","negative","concern","concerns","fear","fears",
    "cut","cuts","warning","warnings","risk","risks","default","crash"
}

def score_sentiment(text):
    words = set(text.lower().split())
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    if pos > neg: return "positive"
    if neg > pos: return "negative"
    return "neutral"


# ── RSS News ─────────────────────────────────────────────────────────────────
def fetch_rss_feed(url, max_items=6):
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                published = datetime.datetime(*entry.published_parsed[:6]).isoformat()
            title   = entry.get("title", "").strip()
            summary = entry.get("summary", "")[:300].strip()
            items.append({
                "title":     title,
                "link":      entry.get("link", ""),
                "summary":   summary,
                "published": published,
                "source":    feed.feed.get("title", ""),
                "sentiment": score_sentiment(title + " " + summary)
            })
        return items
    except Exception:
        return []


def fetch_all_news():
    news = {"macro_global": [], "serbia": []}

    for category, feeds in RSS_FEEDS.items():
        for source_name, url in feeds:
            news[category].extend(fetch_rss_feed(url, max_items=6))

    if NEWS_API_KEY:
        try:
            for query, tag in [
                ("macroeconomics ECB Fed interest rates inflation", "macro_global"),
                ("Serbia economy finance NBS inflation GDP",        "serbia"),
            ]:
                url = (
                    "https://newsapi.org/v2/everything?"
                    f"q={requests.utils.quote(query)}"
                    "&language=en&sortBy=publishedAt&pageSize=8"
                    f"&apiKey={NEWS_API_KEY}"
                )
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    for art in r.json().get("articles", []):
                        title   = art.get("title", "").strip()
                        summary = (art.get("description") or "")[:300].strip()
                        news[tag].append({
                            "title":     title,
                            "link":      art.get("url", ""),
                            "summary":   summary,
                            "published": art.get("publishedAt", ""),
                            "source":    art.get("source", {}).get("name", "NewsAPI"),
                            "sentiment": score_sentiment(title + " " + summary)
                        })
        except Exception:
            pass

    # Deduplicate
    for cat in news:
        seen, deduped = set(), []
        for item in news[cat]:
            if item["title"] and item["title"] not in seen:
                seen.add(item["title"])
                deduped.append(item)
        news[cat] = deduped

    return news


# ── Key Events ────────────────────────────────────────────────────────────────
def fetch_key_events():
    events = []
    try:
        feed = feedparser.parse("https://www.investing.com/rss/news_301.rss")
        for entry in feed.entries[:10]:
            events.append({
                "title":   entry.get("title", "").strip(),
                "link":    entry.get("link", ""),
                "summary": entry.get("summary", "")[:200].strip(),
            })
    except Exception:
        pass
    return events


# ── Market clock ─────────────────────────────────────────────────────────────
def market_clock():
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    def is_open(open_h, close_h, tz_offset):
        local = now_utc + datetime.timedelta(hours=tz_offset)
        if local.weekday() >= 5:
            return False
        h = local.hour + local.minute / 60
        return open_h <= h < close_h
    return {
        "NYSE/NASDAQ": is_open(9.5,  16.0, -4),
        "LSE":         is_open(8.0,  16.5,  1),
        "Frankfurt":   is_open(9.0,  17.5,  2),
        "Tokyo":       is_open(9.0,  15.5,  9),
        "Hong Kong":   is_open(9.5,  16.0,  8),
        "Belgrade":    is_open(9.0,  14.0,  2),
    }


# ── Assemble & Save ───────────────────────────────────────────────────────────
def sentiment_summary(items):
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for i in items:
        counts[i.get("sentiment", "neutral")] += 1
    return counts


def build_payload():
    print("Fetching market data (closing prices)...")
    market = fetch_market_data()

    print("Fetching NBS exchange rates...")
    nbs_rates = fetch_nbs_rates()

    print("Fetching winners/losers...")
    movers = fetch_winners_losers()

    print("Fetching news...")
    news = fetch_all_news()

    print("Fetching key events...")
    events = fetch_key_events()

    payload = {
        "date":              TODAY_STR,
        "generated_at":      datetime.datetime.now(CET).isoformat(),
        "market":            market,
        "nbs_rates":         nbs_rates,
        "movers":            movers,
        "news":              news,
        "key_events":        events,
        "market_clock":      market_clock(),
        "sentiment_summary": {
            "macro":  sentiment_summary(news.get("macro_global", [])),
            "serbia": sentiment_summary(news.get("serbia", [])),
        }
    }

    dated_path  = OUTPUT_DIR / f"daily_{TODAY_STR}.json"
    latest_path = OUTPUT_DIR / "latest.json"
    index_path  = OUTPUT_DIR / "index.json"

    for path in (dated_path, latest_path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    index = []
    if index_path.exists():
        with open(index_path) as f:
            index = json.load(f)
    if TODAY_STR not in index:
        index.append(TODAY_STR)
        index.sort(reverse=True)
    with open(index_path, "w") as f:
        json.dump(index, f, indent=2)

    print(f"Done. Saved: {dated_path}")
    return payload


if __name__ == "__main__":
    build_payload()
