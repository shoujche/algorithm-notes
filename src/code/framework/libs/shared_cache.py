"""三个框架怎么接缓存：Django LocMem、Flask-Caching、redis-py。

运行：pip install django flask-caching redis fakeredis && python shared_cache.py
LocMem 和 SimpleCache 是进程内的；Redis 才是多个进程共用的一份。
没装 Redis 时，脚本用 fakeredis 跑同一套 redis-py 调用。
"""

import json
import os

import django
import fakeredis
import redis
from django.conf import settings
from flask import Flask
from flask_caching import Cache

settings.configure(
    CACHES={
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        # 生产把后端换成下面两个之一（都是 Django 自带，Redis 那个不需要 django-redis）：
        # "django.core.cache.backends.redis.RedisCache"            LOCATION = redis://host:6379/0
        # "django.core.cache.backends.memcached.PyMemcacheCache"   LOCATION = "host:11211"
    }
)
django.setup()

from django.core.cache import cache as dj_cache


def redis_client():
    """REDIS_URL 形如 redis://localhost:6379/0，不要把密码写进代码。"""
    url = os.environ.get("REDIS_URL")
    if url:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
        return client, "redis"
    return fakeredis.FakeRedis(decode_responses=True), "fakeredis"


def get_or_set(client, key: str, ttl: int, produce):
    """缓存未命中时计算，并用 NX 避免后写的人覆盖先写进去的值。"""
    cached = client.get(key)
    if cached is not None:
        return json.loads(cached), "hit"
    value = produce()
    client.set(key, json.dumps(value), ex=ttl, nx=True)
    stored = client.get(key)
    return json.loads(stored), "miss"


if __name__ == "__main__":
    # 1) Django：进程内 LocMem。get_or_set 的回调只在未命中时执行。
    calls = []
    assert dj_cache.get("missing") is None
    assert dj_cache.get_or_set("hot", lambda: calls.append(1) or ["Ada"]) == ["Ada"]
    assert dj_cache.get_or_set("hot", lambda: calls.append(1) or ["nope"]) == ["Ada"]
    assert calls == [1]
    dj_cache.delete("hot")

    # 2) Flask-Caching：SimpleCache 同样是进程内。Redis 只要改 CACHE_TYPE 和 CACHE_REDIS_URL。
    app = Flask(__name__)
    flask_cache = Cache(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 60})
    with app.app_context():
        assert flask_cache.get("k") is None
        flask_cache.set("k", {"n": 1}, timeout=30)
        assert flask_cache.get("k") == {"n": 1}
        assert flask_cache.add("k", {"n": 2}) is False       # 已存在就不覆盖
        flask_cache.delete("k")

    # 3) redis-py：三个框架都能直接用。值是字符串，结构化数据自己 json。
    client, backend = redis_client()
    calls.clear()
    key = "bookshop:hot-titles"
    first, how = get_or_set(client, key, 30, lambda: calls.append(1) or ["Peewee"])
    second, how2 = get_or_set(client, key, 30, lambda: calls.append(1) or ["nope"])
    assert (first, how, second, how2, calls) == (["Peewee"], "miss", ["Peewee"], "hit", [1])
    assert client.ttl(key) > 0
    client.delete(key)

    print(f"django locmem ok  flask simplecache ok  {backend} hit-after-miss ok")
