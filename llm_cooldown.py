"""Short-circuit repeated attempts to an unreachable local LLM.

When Ollama is not running, a connection attempt to its host is often
silently dropped instead of refused, so it blocks for the full TCP connect
timeout (several seconds). After one failure we remember the outage and skip
further attempts for a short window, so the rule-based fallback answers
instantly instead of stalling on every message.
"""

import threading
import time

_lock = threading.Lock()
_cooldown_until = 0.0
_COOLDOWN_SECONDS = 60


def is_ollama_on_cooldown() -> bool:
    global _cooldown_until
    with _lock:
        return time.time() < _cooldown_until


def mark_ollama_unavailable() -> None:
    global _cooldown_until
    with _lock:
        _cooldown_until = time.time() + _COOLDOWN_SECONDS
