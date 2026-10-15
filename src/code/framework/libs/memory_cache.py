"""进程内缓存：cachetools 的 TTLCache / LRUCache。只活在当前进程的内存里。

运行：pip install cachetools && python memory_cache.py
gunicorn 开 4 个 worker 就是 4 份互不相通的缓存；多进程、多机器要换 Redis / Memcached。
"""

import threading
import time

import cachetools

# maxsize 是条目上限，ttl 是秒。过期用单调时钟，不受系统时间回拨影响。
ttl_cache: cachetools.TTLCache[str, list[str]] = cachetools.TTLCache(maxsize=128, ttl=0.2)
# LRU：满了淘汰最久没被访问的。cachetools 的缓存不是线程安全的，写多线程要加锁。
lru_cache: cachetools.LRUCache[str, int] = cachetools.LRUCache(maxsize=2)
lock = threading.Lock()


@cachetools.cached(ttl_cache, lock=lock)
def hot_titles(topic: str) -> list[str]:
    """同一组参数在 ttl 内只计算一次。lock 让并发的第二次调用等到第一次写完再读。"""
    produced.append(topic)
    return [f"{topic}-1", f"{topic}-2"]


produced: list[str] = []


def get_or_set(cache, key, produce):
    """没有装饰器时的手写写法。先查再算，查和写都要在同一把锁里。"""
    with lock:
        try:
            return cache[key]
        except KeyError:
            value = produce()
            cache[key] = value
            return value


if __name__ == "__main__":
    assert hot_titles("flask") == hot_titles("flask") == ["flask-1", "flask-2"]
    assert produced == ["flask"]                 # 第二次命中，没有重算

    time.sleep(0.25)                             # 超过 ttl
    assert hot_titles("flask") == ["flask-1", "flask-2"]
    assert produced == ["flask", "flask"]        # 过期后重算

    lru_cache["a"] = 1
    lru_cache["b"] = 2
    lru_cache["a"]                               # 访问 a，a 变成最近使用
    lru_cache["c"] = 3                           # 容量 2，淘汰最久未用的 b
    evicted = list(lru_cache.items())
    assert evicted == [("a", 1), ("c", 3)]

    calls = []
    value = get_or_set(lru_cache, "report", lambda: calls.append(1) or {"n": 1})
    again = get_or_set(lru_cache, "report", lambda: calls.append(1) or {"n": 2})
    assert value == again == {"n": 1} and calls == [1]

    print(f"ttl recomputes={len(produced)}  lru={evicted}  memoized={again}")
