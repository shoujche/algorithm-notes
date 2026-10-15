# 三个框架的常用第三方库：数据库与缓存

> 系列文档：[Django](./django.md) · [Flask](./flask.md) · [FastAPI](./fastapi.md) · **常用第三方库**
>
> Django 自带 ORM 和缓存框架；Flask / FastAPI 的数据库和缓存都要自己选库。这一篇只讲最常用的两类：**ORM（SQLAlchemy、Peewee）** 和 **缓存（进程内 cachetools、Redis、Memcached）**，以及三个框架各自怎么接。
>
> 验证环境：Python 3.12 · Peewee 4.5.3 · SQLAlchemy 2.1.4 · cachetools 7.2.1 · redis-py 8.1.0 · pymemcache 4.0.0 · Flask-Caching 2.5.1 · Django 6.1.2（2026-10）。文中脚本都在本地跑过。

---

## 目录

1. [先看对照表](#1-先看对照表)
2. [SQLAlchemy](#2-sqlalchemy)
3. [Peewee](#3-peewee)
4. [三个 ORM 怎么对应](#4-三个-orm-怎么对应)
5. [进程内缓存](#5-进程内缓存)
6. [Redis](#6-redis)
7. [Memcached](#7-memcached)
8. [三个框架分别怎么接](#8-三个框架分别怎么接)
9. [面试题](#9-面试题)
10. [常见坑](#10-常见坑)

---

## 1. 先看对照表

| 需求 | Django | Flask | FastAPI |
|---|---|---|---|
| 默认数据库层 | 自带 Django ORM | 无。最常见是 **Flask-SQLAlchemy** | 无。直接用 **SQLAlchemy**，或 SQLModel |
| 更轻的 ORM | 很少再加。Django ORM 已经绑死迁移、Admin、DRF | **Peewee** | **Peewee**（同步，路由写 `def`） |
| 异步数据库访问 | ORM 的 `a*` 方法，底层仍走线程 | 不适合。async 视图不提高吞吐 | SQLAlchemy 2 的 `asyncio` 扩展 + 异步驱动 |
| 进程内缓存 | 自带 `LocMemCache` | Flask-Caching 的 `SimpleCache` | **cachetools**，或 `functools.lru_cache` |
| 多进程共享缓存 | 自带 `RedisCache` / `PyMemcacheCache` | Flask-Caching 的 `RedisCache` / `MemcachedCache` | **redis-py** / **pymemcache**，自己写依赖 |

选型就两句话：

- 数据库：Django 用自带 ORM；Flask 和 FastAPI 用 SQLAlchemy。Peewee 适合小服务、脚本、不想上 SQLAlchemy 那套 Session 的场景。
- 缓存：单个进程里的热点用内存缓存；gunicorn 多 worker、多台机器，必须用 Redis 或 Memcached，否则每个进程各缓存各的。

---

## 2. SQLAlchemy

SQLAlchemy 是 Flask 和 FastAPI 的事实标准，分两层：

- **Core**：SQL 表达式，`select()` / `insert()` / `update()`。
- **ORM**：`Session` 跟踪对象，`session.add()` 后 `session.commit()` 才落库。这是 Data Mapper，对象自己不会 `save()`。

2.0 风格的模型用 `Mapped` + `mapped_column`。防 N+1 用 `joinedload`（JOIN，多对一）和 `selectinload`（第二条 `IN` 查询，一对多）。迁移用 Alembic；Flask 里通常再包一层 Flask-Migrate。

三个框架里它的差别不在查询语法，在 **Session 谁来管**：

| 框架 | Session 从哪来 |
|---|---|
| Flask | Flask-SQLAlchemy 把 scoped session 绑在应用上下文上，请求结束自动移除 |
| FastAPI | `yield` 依赖注入到参数，请求结束跑清理段。同步 Session 配 `def` 路由 |
| Django | 不用它。要在 Django 里用，得自己管引擎和事务，和 Django ORM 的事务是两套 |

查询写法、`joinedload` 和扣库存的可运行脚本在 [Flask 手记](./flask.md) 第 5 节和 [FastAPI 手记](./fastapi.md) 第 9 节，这里不重复。

> **三框架对比**
> Django 的 `Book.objects.filter(title__icontains="pee")` ≈ `select(Book).where(Book.title.ilike("%pee%"))`。
> `select_related` ≈ `joinedload`，`prefetch_related` ≈ `selectinload`，`F("stock") - 1` ≈ `Book.stock - 1`。

---

## 3. Peewee

Peewee 是一个小得多的 ORM：一个模型类加一个数据库对象就能查。API 看起来像 Django（`Model.create`、`Model.select().where()`、`DoesNotExist`），但没有 Admin、没有迁移框架（要迁移另加 peewee-migrate 或自己管）、连接也不会按请求自动开关。

```bash
pip install peewee
```

模型先写，数据库用 `DatabaseProxy` 晚点绑定。测试可以 `initialize(SqliteDatabase(":memory:"))`，生产再换成 Postgres。

```python
import peewee as pw

db = pw.DatabaseProxy()

class Author(pw.Model):
    name = pw.CharField(unique=True)
    class Meta:
        database = db

class Book(pw.Model):
    title = pw.CharField(index=True)
    price = pw.DecimalField(max_digits=8, decimal_places=2)
    stock = pw.IntegerField(default=0)
    author = pw.ForeignKeyField(Author, backref="books", on_delete="CASCADE")
    class Meta:
        database = db
```

常用写法：

| 操作 | Peewee |
|---|---|
| 创建 | `Book.create(title=..., author=ada)` |
| 查不到就建 | `Author.get_or_create(name="Bob")` → `(obj, created)` |
| 过滤 | `Book.select().where(Book.price > 10, Book.stock > 0)` |
| 取一条 | `.get()`，没有就抛 `DoesNotExist` |
| 按主键 | `Book.get_by_id(1)` |
| 模糊查 | `Book.title.contains("pee")`，生成 `LIKE ?`，参数分开传 |
| 事务 | `with db.atomic():` |
| 建表 | `db.create_tables([Author, Book])`。生产用迁移，不要靠 `create_tables` |

`select()` 也是惰性的，迭代时才发 SQL。

### 外键和 N+1

直接写 `book.author.name`，每本书额外查一次作者。3 本书实测 **4 条 SELECT**（1 + 3）。

两种避免办法，和 Django 一一对应：

```python
# JOIN，一条 SQL。要把 Author 放进 select()，否则 Peewee 不会把作者列取回来
[b.author.name for b in Book.select(Book, Author).join(Author)]

# 两条 SQL：先查作者，再按外键 IN 查书
[len(a.books) for a in pw.prefetch(Author.select(), Book.select())]
```

实测：`join` 是 **1** 条，`prefetch` 是 **2** 条。

### 条件更新

```python
with db.atomic():
    updated = (
        Book.update(stock=Book.stock - 1)
        .where((Book.id == book_id) & (Book.stock > 0))
        .execute()
    )
```

`execute()` 返回影响行数，0 就是没扣成。和 Django 的 `QuerySet.update()` 一样，**已经取到内存里的对象不会跟着变**：更新后旧对象的 `stock` 仍是旧值，要 `Book.get_by_id()` 重新读。

`atomic()` 里抛异常，整块回滚。

完整可运行脚本：`src/code/framework/libs/peewee_orm.py`。

> **三框架对比**
> - Django 项目继续用 Django ORM。Peewee 插进去会有第二套连接和事务，得不偿失。
> - Flask、FastAPI 的小服务可以用 Peewee 少写 Session 样板。模型一多、要异步、要复杂预加载，换 SQLAlchemy。
> - FastAPI 里 Peewee 是同步库，路由写 `def`，让它进线程池。不要在 `async def` 里直接调。

---

## 4. 三个 ORM 怎么对应

| | Django ORM | SQLAlchemy 2 | Peewee |
|---|---|---|---|
| 风格 | Active Record，`obj.save()` | Data Mapper，`session.commit()` | Active Record，`Model.create()` |
| 过滤 | `filter(price__gt=10)` | `where(Book.price > 10)` | `where(Book.price > 10)` |
| 取一条 | `.get()` / `.first()` | `session.scalars(stmt).one()` / `.first()` | `.get()` / `.first()` |
| 不存在 | `DoesNotExist` | `NoResultFound` 或自己判断 `None` | `DoesNotExist` |
| 多对一预加载 | `select_related` | `joinedload` | `select(Book, Author).join(Author)` |
| 一对多预加载 | `prefetch_related` | `selectinload` | `prefetch()` |
| 原子加减 | `F("stock") - 1` | `Book.stock - 1` | `Book.stock - 1` |
| 事务 | `transaction.atomic()` | `session.begin()` / `with session.begin()` | `db.atomic()` |
| 迁移 | 自带 | Alembic（Flask 用 Flask-Migrate） | 另外配，或不管 |

---

## 5. 进程内缓存

进程内缓存就是一个带淘汰策略的字典，存在当前进程的堆里。没有网络开销，也没有序列化。worker 一多就失效：4 个 worker 是 4 份缓存，重启即丢，也不能当锁用。

### cachetools

```bash
pip install cachetools
```

| 类 | 行为 |
|---|---|
| `TTLCache(maxsize, ttl)` | 条目最多 `maxsize` 个，写入后 `ttl` 秒过期 |
| `LRUCache(maxsize)` | 满了淘汰最久没被访问的 |
| `LFUCache` / `RRCache` | 按访问次数淘汰 / 随机淘汰 |

`@cachetools.cached(cache, lock=threading.Lock())` 按参数缓存函数返回值。**这些缓存不是线程安全的**，多线程必须加锁。锁还有一个副作用：两个线程同时未命中时，后一个会等到前一个写完，于是第二次变成命中，不会把同一份数据算两遍。

实测 `ttl=0.2`：连续两次调用只计算 1 次；睡 0.25 秒后再调用，会再计算 1 次。`LRUCache(maxsize=2)` 依次放入 a、b，访问 a，再放入 c，留下的是 a 和 c，b 被淘汰。

`functools.lru_cache` 是标准库版本：线程安全、按参数缓存，但 **没有 TTL**，不适合会过期的数据。适合纯函数（解析配置、编译正则）。

### 框架自带的进程内后端

不必为了进程内缓存专门装 cachetools，框架自己也有：

| 框架 | 后端 | 说明 |
|---|---|---|
| Django | `django.core.cache.backends.locmem.LocMemCache` | `django.core.cache.cache`，`get` / `set` / `get_or_set` / `delete` |
| Flask | Flask-Caching 的 `CACHE_TYPE = "SimpleCache"` | 要在应用上下文里用 |
| FastAPI | 没有内置 | 用 cachetools，或在依赖里包一个缓存对象 |

Django 的 `get_or_set(key, default)`：`default` 可以是一个零参数 callable，**只有未命中才调用**。Flask-Caching 的 `add(key, value)` 是「没有才写入」，已存在返回 `False`。

可运行脚本：`memory_cache.py`（cachetools）、`shared_cache.py` 的前半（Django LocMem + Flask SimpleCache）。

---

## 6. Redis

Redis 是三个框架共用缓存的默认选择。除了缓存，它还经常当 Celery / RQ 的 broker、分布式锁、发布订阅。缓存场景记住三件事：设过期时间、值要能序列化、key 要带前缀。

```bash
pip install redis
```

```python
import json, os, redis

client = redis.Redis.from_url(
    os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
    decode_responses=True,          # 返回 str 而不是 bytes
)

def get_or_set(key: str, ttl: int, produce):
    cached = client.get(key)
    if cached is not None:
        return json.loads(cached)
    value = produce()
    # nx=True：已经有人写入就不要覆盖
    client.set(key, json.dumps(value), ex=ttl, nx=True)
    return json.loads(client.get(key))
```

- `ex` 是秒。缓存一定要有 TTL，否则内存只增不减。
- `decode_responses=True` 之后存取都是 `str`。字典、列表自己 `json`。不要 `pickle` 不可信的缓存内容。
- key 加业务前缀，比如 `bookshop:hot-titles`，避免和其他服务撞车。
- 地址和密码放 `REDIS_URL`，不要写进代码。

未命中时多个 worker 会同时去算（缓存击穿）。`nx=True` 只保证后写的人不覆盖先写的结果，**挡不住重复计算**。要真正只算一次，得另加一把短期锁，或者接受这份重复。

异步 FastAPI 用 `redis.asyncio.Redis`（redis-py 8 自带），在 lifespan 里建一个客户端挂到 `app.state`，不要每个请求 `from_url` 一次。同步的 `redis.Redis` 调用是阻塞的，放在 `def` 路由或 `run_in_threadpool` 里。

`shared_cache.py` 在没有 `REDIS_URL` 时用 fakeredis 跑这同一套调用，方便本地验证；fakeredis 只是测试替身，不是生产客户端。

---

## 7. Memcached

Memcached 只做缓存：内存键值、有 TTL、没有持久化、没有 Redis 那些数据结构。缓存场景它够用，而且协议简单；需要列表、发布订阅、分布式锁时用 Redis。

```bash
pip install pymemcache
```

```python
from pymemcache.client.base import Client

client = Client(("127.0.0.1", 11211), default_noreply=False)
client.set("bookshop:hot", b"1", expire=30)    # expire 单位是秒，0 表示不过期
value = client.get("bookshop:hot")
```

pymemcache 4 的 `Client` 默认 `default_noreply=True`：`set` 发出去就返回，返回值是 `None`，你不知道服务端有没有收下。要拿布尔结果，构造时传 `default_noreply=False`。默认 key 按 ASCII 编码，非 ASCII 的 key 要 `allow_unicode_keys=True`。

Django 和 Flask 都有现成后端，一般不用手写这个客户端：

- Django：`django.core.cache.backends.memcached.PyMemcacheCache`，`LOCATION` 写 `"127.0.0.1:11211"`。
- Flask-Caching：`CACHE_TYPE = "MemcachedCache"`。

---

## 8. 三个框架分别怎么接

### Django：用自带的 cache 框架，换后端不改业务代码

```python
import os

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "KEY_PREFIX": "bookshop",
    }
}
```

业务侧始终是 `from django.core.cache import cache`。开发可以用 `LocMemCache`，测试用 `DummyCache`（什么都不记，避免测试互相污染）。整页缓存用 `@cache_page`。Django 4.0 起 Redis 后端是内置的，不再需要 django-redis。

数据库继续用 Django ORM。这一篇的 SQLAlchemy / Peewee 是讲给 Flask 和 FastAPI 的。

### Flask：Flask-SQLAlchemy + Flask-Caching

```python
from flask_caching import Cache

cache = Cache()

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        CACHE_TYPE="RedisCache",
        CACHE_REDIS_URL=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        CACHE_KEY_PREFIX="bookshop:",
        CACHE_DEFAULT_TIMEOUT=300,
    )
    cache.init_app(app)
    return app
```

和数据库扩展一样：模块顶层创建，工厂里 `init_app`。视图和命令里用之前要有应用上下文。数据库用 Flask-SQLAlchemy，见 [Flask 手记](./flask.md) 第 5 节。

### FastAPI：库直接用，用依赖和 lifespan 接进去

```python
import redis.asyncio as redis
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.redis.aclose()
```

路由里要么 `request.app.state.redis`，要么写一个 `Depends` 把客户端注进去。数据库用 SQLAlchemy 的 session 依赖，见 [FastAPI 手记](./fastapi.md) 第 9 节。进程内的小缓存直接用 cachetools，注意它不跨 worker。

---

## 9. 面试题

**Q1：Django ORM、SQLAlchemy、Peewee 怎么选？**
Django 项目用 Django ORM，它和迁移、Admin、DRF 是一套的。Flask 和 FastAPI 优先 SQLAlchemy：表达力够，异步、预加载、Alembic 都成熟。Peewee 适合模型少、想少写 Session 样板的小服务，API 接近 Django，但没有迁移和异步。不建议在 Django 里再引入第二个 ORM。

**Q2：进程内缓存和 Redis 缓存差在哪？**
进程内缓存就是本进程内存里的一个字典，没有网络开销，但每个 worker 一份，重启就没了，也不能跨机器。Redis 是独立进程，所有 worker 共用一份，可以设 TTL，机器重启默认也不丢（看持久化配置），代价是一次网络往返和序列化。单进程、可丢的热点用内存；多进程或多实例用 Redis 或 Memcached。

**Q3：为什么缓存键要设 TTL？**
没有过期的缓存会一直占内存，而且数据库改了它也不知道。TTL 让数据最多旧一个周期。更新数据的地方可以再主动 `delete` 相关 key，不必干等过期。

**Q4：什么是缓存击穿？**
一个热点 key 过期的瞬间，大量请求同时发现未命中，一起打到数据库。`set(..., nx=True)` 只能避免互相覆盖，不能避免重复计算。处理办法是加短锁让一个人去加载，或者热点 key 逻辑过期、后台提前刷新。

**Q5：cachetools 为什么要加锁？**
`TTLCache` 和 `LRUCache` 不保证线程安全，并发读写会坏掉内部结构。`@cached(..., lock=threading.Lock())` 把一次「查—算—写」串起来，后来的线程会看到先到的结果，而不是再算一遍。gunicorn 的多进程各自有一把锁，锁解决不了跨进程的问题。

**Q6：FastAPI 里用同步的 Peewee 或 redis.Redis 要注意什么？**
它们的调用会阻塞。路由写成普通 `def`，FastAPI 会丢到线程池；写在 `async def` 里会堵住整个事件循环。异步路径用 SQLAlchemy asyncio 和 `redis.asyncio`。

---

## 10. 常见坑

| 坑 | 正确做法 |
|---|---|
| 开了多个 worker 还用 LocMem / cachetools 当共享缓存 | 换 Redis 或 Memcached |
| Redis 的 `set` 不写 `ex` | 缓存键都带 TTL |
| 把 ORM 对象直接塞进 Redis | 先变成 dict / JSON。连接和身份信息不能跨进程 |
| `pickle` 缓存内容 | 用 JSON。不可信数据不要反序列化成对象 |
| Peewee `book.author.name` 放在循环里 | `select(Book, Author).join(Author)` 或 `prefetch` |
| SQL `UPDATE` 之后继续用旧对象的属性 | 重新 `get`，内存里的对象不会自己刷新 |
| pymemcache 默认 `noreply=True`，以为 `set` 返回了成功 | 需要结果就 `default_noreply=False` |
| FastAPI 每个请求新建 Redis 连接 | lifespan 里建一个，全程复用 |
| 在 `async def` 里调用 Peewee、同步 redis | 改成 `def` 路由，或换异步客户端 |
| 缓存了用户相关数据，key 里却没有用户 id | key 带上用户标识，避免串数据 |
| 连接串里写死密码 | `REDIS_URL` 从环境变量读 |
