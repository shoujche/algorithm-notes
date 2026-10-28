"""分布式锁：一条 SET key token NX PX，解锁用 Lua 核对 token 再删除。

运行：pip install redis fakeredis lupa && python dist_lock.py
fakeredis 执行 EVAL 需要 lupa。token 是这次加锁的随机值，不是访问 Redis 的口令。
"""

import uuid

import fakeredis

# 只有值仍是自己的 token 时才删除。两条命令分开做，会把别人刚拿到的锁删掉。
UNLOCK = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
else
  return 0
end
"""


def acquire(client, key: str, token: str, ttl_ms: int) -> bool:
    # NX 表示键不存在才写入；PX 把过期时间放进同一次命令。
    # SETNX 再 EXPIRE 是两次往返，进程死在中间时锁没有过期时间。
    return client.set(key, token, nx=True, px=ttl_ms) is True


def release(client, key: str, token: str) -> bool:
    return client.eval(UNLOCK, 1, key, token) == 1


# 业务还没做完、锁快到期时，只有持有者能把过期时间往后推。做完必须停止续期。
RENEW = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('pexpire', KEYS[1], ARGV[2])
else
  return 0
end
"""


def renew(client, key: str, token: str, ttl_ms: int) -> bool:
    return client.eval(RENEW, 1, key, token, ttl_ms) == 1


if __name__ == "__main__":
    client = fakeredis.FakeRedis(decode_responses=True)
    key = "lock:order:42"
    holder = str(uuid.uuid4())
    other = str(uuid.uuid4())

    assert acquire(client, key, holder, 30_000) is True
    assert acquire(client, key, other, 30_000) is False
    assert release(client, key, other) is False
    assert client.get(key) == holder
    assert renew(client, key, other, 30_000) is False
    assert renew(client, key, holder, 30_000) is True
    assert release(client, key, holder) is True
    assert client.get(key) is None
    assert acquire(client, key, other, 30_000) is True

    # redis-py 的 Lock 用的是同一套 SET NX PX 和 Lua。blocking_timeout=0 表示拿不到就返回。
    client.delete(key)
    first = client.lock(key, timeout=10, blocking_timeout=0)
    second = client.lock(key, timeout=10, blocking_timeout=0)
    assert first.acquire(blocking=False) is True
    assert second.acquire(blocking=False) is False
    first.release()
    assert second.acquire(blocking=False) is True
