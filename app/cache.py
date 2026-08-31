"""Small in-process TTL cache, carried over from the original FinSight backend.

Every Gemini and Yahoo call is either identical for all users (market
commentary), identical for the same input (flashcards for a module), or
identical until the user's own data changes (the coach). Without a cache, one
request per user is one upstream call for content that did not change.

In-process on purpose: the service runs a single worker, so a dict is enough
and adds no dependency.
"""

import hashlib
import json
import threading
import time


class TTLCache:
    """Thread-safe key/value store where entries expire after a set time."""

    def __init__(self, max_entries: int = 256):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if time.time() >= expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value, ttl_seconds: float) -> None:
        with self._lock:
            if len(self._store) >= self._max_entries:
                self._evict_locked()
            self._store[key] = (time.time() + ttl_seconds, value)

    def _evict_locked(self) -> None:
        now = time.time()
        for key in [k for k, (exp, _) in self._store.items() if exp <= now]:
            del self._store[key]
        if len(self._store) >= self._max_entries:
            oldest = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest]

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = self._misses = 0

    def stats(self) -> dict:
        with self._lock:
            now = time.time()
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "live": sum(1 for exp, _ in self._store.values() if exp > now),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else None,
            }


def make_key(*parts) -> str:
    """Stable cache key from arbitrary JSON-serialisable parts, hashed because
    some parts (a whole module's text) are too long to be a dict key."""
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


cache = TTLCache()

# How long each kind of response stays fresh.
TTL_MARKET_QUOTES = 60
TTL_MARKET_LAST_GOOD = 12 * 60 * 60      # stale fallback when Yahoo throttles
TTL_MARKET_INSIGHT = 15 * 60             # identical for every user
TTL_FLASHCARDS = 24 * 60 * 60            # pure function of the module text
TTL_COACH = 60 * 60                      # key already includes the user's data
