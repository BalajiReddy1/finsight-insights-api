"""Live Indian-market quotes from Yahoo Finance, collected politely.

Yahoo rate-limits by IP and a shared host gets throttled far sooner than a
laptop. When a fetch fails, the last quotes that were genuinely fetched are
served instead of inventing numbers: they are real, just not current, and the
caller is told which via the X-Cache header on the route.
"""

import yfinance as yf

from app.cache import TTL_MARKET_LAST_GOOD, TTL_MARKET_QUOTES, cache

TICKERS = {
    "^NSEI": "NIFTY 50",
    "^BSESN": "SENSEX",
    "GC=F": "Gold (Futures)",
    "INR=X": "USD / INR",
}


def fetch_quotes() -> tuple[list[dict], bool]:
    """Return (quotes, from_cache). Raises only if there is nothing to serve."""
    fresh = cache.get("market:quotes")
    if fresh is not None:
        return fresh, True

    try:
        data = yf.Tickers(" ".join(TICKERS))
        quotes = []
        for symbol, name in TICKERS.items():
            info = data.tickers[symbol].fast_info
            price = info.last_price
            prev = info.previous_close
            quotes.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "prev_close": prev,
                    "change_percent": ((price - prev) / prev) * 100 if prev else 0.0,
                }
            )
    except Exception as exc:
        stale = cache.get("market:quotes:last")
        if stale is not None:
            print(f"[market] yfinance failed ({exc}); serving last known quotes")
            return stale, True
        raise

    cache.set("market:quotes", quotes, TTL_MARKET_QUOTES)
    cache.set("market:quotes:last", quotes, TTL_MARKET_LAST_GOOD)
    return quotes, False
