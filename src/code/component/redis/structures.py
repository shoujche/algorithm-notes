"""五种常用结构。选结构看的是命令在服务端做什么，不是把数据拉回 Python 再处理。"""

import fakeredis


def save_user(client, user_id: str, name: str, city: str) -> None:
    # 哈希：一个对象的多个字段共用一个键。改城市不用重写整个对象。
    client.hset(f"user:{user_id}", mapping={"name": name, "city": city})


def push_recent(client, user_id: str, title: str) -> None:
    # 列表：左边是最新。LRANGE 取一段，适合最近浏览，不适合需要确认的任务队列。
    key = f"user:{user_id}:recent"
    client.lpush(key, title)
    client.ltrim(key, 0, 99)


def tag_article(client, article_id: str, *tags: str) -> None:
    # 集合：成员不重复。判断标签在不在是 SISMEMBER，不用把集合取回来。
    client.sadd(f"article:{article_id}:tags", *tags)


def add_score(client, board: str, member: str, score: float) -> None:
    # 有序集合：成员带分数。排行榜用 ZREVRANGE，范围查询用 ZRANGEBYSCORE。
    client.zadd(board, {member: score})


if __name__ == "__main__":
    client = fakeredis.FakeRedis(decode_responses=True)
    save_user(client, "7", "Ada", "London")
    assert client.hget("user:7", "city") == "London"
    client.hset("user:7", "city", "Paris")
    assert client.hgetall("user:7") == {"name": "Ada", "city": "Paris"}

    push_recent(client, "7", "链表")
    push_recent(client, "7", "Redis")
    assert client.lrange("user:7:recent", 0, 0) == ["Redis"]

    tag_article(client, "9", "cache", "lock", "cache")
    assert client.sismember("article:9:tags", "lock") == 1
    assert client.scard("article:9:tags") == 2

    add_score(client, "rank", "ada", 10)
    add_score(client, "rank", "grace", 30)
    add_score(client, "rank", "linus", 20)
    assert client.zrevrange("rank", 0, 1) == ["grace", "linus"]
    assert client.zrangebyscore("rank", 15, 25) == ["linus"]
