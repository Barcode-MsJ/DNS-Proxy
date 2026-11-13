from dnsproxy.cache import DNSCache


class FakeClock:
    def __init__(self): self.now = 100.0
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds


def test_ttl_decreases_and_expires():
    clock = FakeClock()
    cache = DNSCache(clock=clock)
    cache.put("a.example", "192.0.2.1", 5)
    clock.advance(2)
    assert cache.get("a.example").ttl == 3
    clock.advance(3)
    assert cache.get("a.example") is None


def test_fifo_capacity_evicts_oldest_inserted_entry():
    clock = FakeClock()
    cache = DNSCache(max_entries=2, clock=clock)
    cache.put("one.example", "192.0.2.1", 30)
    cache.put("two.example", "192.0.2.2", 30)
    cache.put("three.example", "192.0.2.3", 30)
    assert [x[0] for x in cache.snapshot()] == ["two.example", "three.example"]


def test_cache_refresh_moves_key_to_newest_fifo_position():
    cache = DNSCache(max_entries=2)
    cache.put("one", "192.0.2.1", 30)
    cache.put("two", "192.0.2.2", 30)
    cache.put("one", "192.0.2.3", 30)
    cache.put("three", "192.0.2.4", 30)
    assert [x[0] for x in cache.snapshot()] == ["one", "three"]


def test_zero_ttl_is_not_cached():
    cache = DNSCache()
    cache.put("zero", "192.0.2.1", 0)
    assert cache.get("zero") is None
