"""
Prayash — Redis Store Unit Tests
=================================
``_RedisStore`` (security.py) maps the dict-like store API onto a Redis
client. These tests exercise that mapping against a tiny in-process stub of
the redis-py API (``get``/``set``/``exists``/``delete``/``scan_iter`` and a
transactional pipeline with sorted-set ops) so no Redis server is required.

The production connection/fallback logic in ``_build_redis_client`` is not
tested here — it only runs when ``REDIS_URL`` is set, which the suite keeps
empty.
"""

from __future__ import annotations

from security import _RedisStore


# ── Minimal redis-py stub ───────────────────────────────────────────
class _FakePipeline:
    """Mimics redis-py's pipeline: ops are buffered, executed together."""

    def __init__(self, client: _FakeRedis) -> None:
        self._client = client
        self._ops: list[tuple] = []

    def zremrangebyscore(self, key: str, _min: str, max_: float) -> _FakePipeline:
        self._ops.append(("zrem", key, max_))
        return self

    def zadd(self, key: str, mapping: dict) -> _FakePipeline:
        self._ops.append(("zadd", key, mapping))
        return self

    def zcard(self, key: str) -> _FakePipeline:
        self._ops.append(("zcard", key))
        return self

    def expire(self, key: str, ttl: int) -> _FakePipeline:
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self) -> list:
        results: list = []
        for op in self._ops:
            kind = op[0]
            if kind == "zrem":
                _, key, max_ = op
                zs = self._client._zsets.setdefault(key, {})
                for m in [m for m, s in list(zs.items()) if s <= max_]:
                    del zs[m]
                results.append(0)
            elif kind == "zadd":
                _, key, mapping = op
                self._client._zsets.setdefault(key, {}).update(mapping)
                results.append(len(mapping))
            elif kind == "zcard":
                results.append(len(self._client._zsets.get(op[1], {})))
            elif kind == "expire":
                self._client._ttl[op[1]] = op[2]
                results.append(True)
        return results


class _FakeRedis:
    """In-process stand-in for ``redis.Redis`` (string-key store + zsets)."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._ttl: dict[str, int] = {}
        self._zsets: dict[str, dict] = {}

    def get(self, key: str) -> bytes | None:
        return self._data.get(key)

    def set(self, key: str, value: bytes, ex: int | None = None) -> bool:
        self._data[key] = value
        if ex is not None:
            self._ttl[key] = ex
        return True

    def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._ttl.pop(key, None)
                removed += 1
        return removed

    def scan_iter(self, match: str) -> list[str]:
        prefix = match.split("*")[0]
        return [k for k in self._data if k.startswith(prefix)]

    def pipeline(self, transaction: bool = True) -> _FakePipeline:
        return _FakePipeline(self)


def _make_store(prefix: str = "test", ttl: int = 300) -> tuple[_RedisStore, _FakeRedis]:
    client = _FakeRedis()
    return _RedisStore(client, prefix, ttl), client


# ── Dict-like API ───────────────────────────────────────────────────
def test_setitem_get_roundtrips_json_with_ttl() -> None:
    store, client = _make_store()
    store["ip:user"] = (3, 12345.0)

    assert store.get("ip:user") == [3, 12345.0]  # JSON arrays unpack like tuples
    assert "ip:user" in store
    assert store.get("missing") is None
    assert store.get("missing", "fallback") == "fallback"
    # TTL equals the store window so stale keys are reclaimed automatically
    assert client._ttl["prayash:test:ip:user"] == 300


def test_pop_removes_and_returns() -> None:
    store, _ = _make_store()
    store["k"] = (1, 2.0)
    assert store.pop("k") == [1, 2.0]
    assert "k" not in store
    assert store.pop("k", "gone") == "gone"


def test_clear_only_touches_own_prefix() -> None:
    # Two stores over the SAME Redis client must not clear each other's keys
    client = _FakeRedis()
    store_a = _RedisStore(client, "a", 300)
    store_b = _RedisStore(client, "b", 300)
    store_a["x"] = 1
    store_b["x"] = 2

    store_a.clear()

    assert client.exists("prayash:a:x") == 0
    assert client.exists("prayash:b:x") == 1


# ── Sliding-window rate limit ───────────────────────────────────────
def test_record_sliding_enforces_limit_atomically() -> None:
    store, client = _make_store()
    key = "1.2.3.4"

    assert store.record_sliding(key, 60, 3) is True
    assert store.record_sliding(key, 60, 3) is True
    assert store.record_sliding(key, 60, 3) is True
    assert store.record_sliding(key, 60, 3) is False  # 4th request blocked

    # A different key is unaffected
    assert store.record_sliding("other", 60, 3) is True
    # Members are unique per call (timestamp + nonce), so count keeps growing
    assert client._zsets["prayash:test:1.2.3.4"] and len(client._zsets["prayash:test:1.2.3.4"]) == 4


def test_record_sliding_sets_expiry() -> None:
    store, client = _make_store()
    store.record_sliding("ip", 60, 5)
    assert client._ttl["prayash:test:ip"] == 60
