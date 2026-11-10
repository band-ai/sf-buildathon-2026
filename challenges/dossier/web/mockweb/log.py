"""The call log: every provider call since the last reset, in order."""
import threading


class Log:
    """A thread-safe, append-only list of call entries."""

    def __init__(self):
        self._lock = threading.Lock()
        self._calls = []

    def record(self, provider, method, *, cost, status, **entry):
        """Append one call; optional `depth`, `query`, `max_results`, `fields`, `urls`,
        `session` (a browser session's id) and `served` (url, text) pairs."""
        served = entry.get("served", ())
        with self._lock:
            self._calls.append({
                "seq": len(self._calls) + 1, "provider": provider, "method": method,
                "depth": entry.get("depth"), "query": entry.get("query"),
                "max_results": entry.get("max_results"), "fields": entry.get("fields"),
                "urls": list(entry.get("urls", ())), "session": entry.get("session"),
                "cost": cost, "status": status,
                "served": [{"url": url, "text": text} for url, text in served]})

    def calls(self):
        """Every entry, oldest first."""
        with self._lock:
            return list(self._calls)

    def clear(self):
        """Forget every entry; numbering starts again at 1."""
        with self._lock:
            self._calls.clear()
