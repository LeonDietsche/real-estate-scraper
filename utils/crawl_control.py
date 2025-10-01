# utils/crawl_control.py
import os, time, random, threading
from contextlib import contextmanager

_MIN = float(os.getenv("CRAWL_MIN_DELAY_SEC", "2.0"))
_JIT = float(os.getenv("CRAWL_JITTER_SEC", "2.0"))
_MAX_DETAIL = int(os.getenv("CRAWL_MAX_DETAIL_PER_RUN", "25"))

_BACKOFF_MIN = float(os.getenv("CRAWL_BACKOFF_MIN", "10"))
_BACKOFF_MAX = float(os.getenv("CRAWL_BACKOFF_MAX", "300"))

_lock = threading.Lock()
_last_ts = 0.0

def _sleep_gap():
    global _last_ts
    with _lock:
        now = time.time()
        gap = (_MIN + random.random() * _JIT)
        wait = max(0.0, (_last_ts + gap) - now)
        if wait > 0:
            time.sleep(wait)
        _last_ts = time.time()

def polite_pause():
    """Call before each networked page.goto()/requests.get()."""
    _sleep_gap()

def capped_range(n: int):
    """Use in detail loops to cap per-run pages."""
    return range(min(n, _MAX_DETAIL))

@contextmanager
def backoff_on_fail():
    """Wrap a risky block; on exception sleep a random backoff."""
    try:
        yield
    except Exception:
        time.sleep(random.uniform(_BACKOFF_MIN, _BACKOFF_MAX))
        raise
