"""旁路缓存：先读缓存，没有再读数据库，然后回填。空值、抖动和锁分别对三种失效。"""

import uuid

import fakeredis

from dist_lock import acquire, release

MISSING = "__missing__"


def cache_aside(client, key: str, ttl: int, load, lock_key: str | None = None):
    cached = client.get(key)
    if cached is not None:
        return None if cached == MISSING else cached

    token = str(uuid.uuid4())
    locked = lock_key is not None and acquire(client, lock_key, token, 5_000)
    if lock_key is not None and not locked:
        # 别人正在装载。再读一次，读不到就让调用方稍后重试。
        cached = client.get(key)
        return None if cached == MISSING else cached

    try:
        value = load()
        # 数据库没有这条记录时也写入短命空值，避免每次都穿透到数据库。
        stored = MISSING if value is None else value
        client.set(key, stored, ex=ttl)
        return value
    finally:
        if locked:
            release(client, lock_key, token)


def jittered_ttl(base: int, spread: int, roll: int) -> int:
    # 同一批键加上不同的余量，避免在同一秒一起过期。
    return base + roll % spread


if __name__ == "__main__":
    client = fakeredis.FakeRedis(decode_responses=True)
    calls = []

    def missing():
        calls.append("db")
        return None

    assert cache_aside(client, "book:404", 30, missing) is None
    assert cache_aside(client, "book:404", 30, missing) is None
    assert calls == ["db"]

    def price():
        calls.append("price")
        return "10"

    assert cache_aside(client, "book:1:price", 30, price, lock_key="lock:book:1") == "10"
    # 锁被别人拿着时，这一次不会再调用数据库。
    assert acquire(client, "lock:book:2", "busy", 5_000) is True
    assert cache_aside(client, "book:2:price", 30, price, lock_key="lock:book:2") is None
    assert calls == ["db", "price"]
    assert jittered_ttl(30, 17, 5) != jittered_ttl(30, 17, 8)
