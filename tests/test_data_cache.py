"""数据缓存单元测试"""

import time

from src.data.cache import DataCache


class TestDataCache:
    def test_set_and_get(self):
        cache = DataCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = DataCache()
        assert cache.get("nonexistent") is None

    def test_get_expired_key(self):
        cache = DataCache(default_ttl=0.1)  # 100ms TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_custom_ttl(self):
        cache = DataCache(default_ttl=10.0)
        cache.set("key1", "value1", ttl=0.1)
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None

    def test_delete_key(self):
        cache = DataCache()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_delete_nonexistent_key(self):
        cache = DataCache()
        cache.delete("nonexistent")  # 不应抛异常

    def test_clear_all(self):
        cache = DataCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_multiple_keys_independent(self):
        cache = DataCache()
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        cache.delete("a")
        assert cache.get("a") is None
        assert cache.get("b") == 2

    def test_overwrite_existing_key(self):
        cache = DataCache()
        cache.set("key1", "old")
        cache.set("key1", "new")
        assert cache.get("key1") == "new"

    def test_clear_empty_cache(self):
        cache = DataCache()
        cache.clear()  # 不应抛异常

    def test_default_ttl_applied(self):
        cache = DataCache(default_ttl=5.0)
        cache.set("key1", "value1")
        entry = cache._cache["key1"]
        assert entry.expires_at > time.time()
        assert entry.expires_at <= time.time() + 5.0
