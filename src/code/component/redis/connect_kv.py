"""键、过期和管道。地址从环境变量读，示例本身用 fakeredis 执行同一批命令。

生产：
    redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
REDIS_URL 形如 redis://localhost:6379/0。密码放在环境变量里，不要写进仓库。
"""

import os

import fakeredis
import redis


def open_client():
    url = os.environ.get("REDIS_URL")
    if url:
        return redis.Redis.from_url(url, decode_responses=True)
    return fakeredis.FakeRedis(decode_responses=True)


def remember_page_view(client, page_id: str) -> int:
    # EX 和 SET 在同一条命令里。键到期后下一次读得到 None。
    client.set(f"page:{page_id}:title", "Algo Notes", ex=60)
    views = client.incr(f"page:{page_id}:views")
    client.expire(f"page:{page_id}:views", 3600)
    return int(views)


def write_many(client, page_ids: list[str]) -> list:
    # pipeline 把多条命令一次发出去，省的是网络往返。
    # 它不是事务：别人的命令仍可能插在这批命令的执行之间。
    pipe = client.pipeline()
    for page_id in page_ids:
        pipe.set(f"page:{page_id}:title", page_id, ex=60)
        pipe.incr(f"page:{page_id}:views")
    return pipe.execute()


if __name__ == "__main__":
    client = fakeredis.FakeRedis(decode_responses=True)
    assert remember_page_view(client, "redis") == 1
    assert client.get("page:redis:title") == "Algo Notes"
    assert client.ttl("page:redis:title") > 0
    assert write_many(client, ["a", "b"]) == [True, 1, True, 1]
