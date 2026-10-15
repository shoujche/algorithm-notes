# FastAPI 手记：核心用法 · 常用方法 · 教程 · 工程实践 · 面试

> 系列文档：[Django](./django.md) · [Flask](./flask.md) · **FastAPI** · [常用第三方库](./libraries.md)
>
> 三份文档用同一个「书店 Bookshop」例子（作者 / 图书 / 库存 / 购买），方便横向对照。文中所有代码都在本地真实跑过测试。
>
> 验证环境：Python 3.12 · FastAPI 0.143.1 · Starlette 1.8.0 · Pydantic 2.14.1 · SQLAlchemy 2.1.4（2026-10）。
>
> 站点「Python 框架」板块的 F03「FastAPI 工程」章节用可运行脚本讲并发模型 / DI / 中间件 / 流式的原理，本文侧重完整用法与工程实践，两者互补。

文中带 **「三框架对比」** 的引用块，专门说明此处与 Django / Flask 的相同与不同。

---

## 目录

1. [定位：FastAPI 是什么、适合什么](#1-定位fastapi-是什么适合什么)
2. [安装与最小应用](#2-安装与最小应用)
3. [请求生命周期与并发模型](#3-请求生命周期与并发模型)
4. [参数声明：路径、查询、请求体、头](#4-参数声明路径查询请求体头)
5. [Pydantic：校验与序列化](#5-pydantic校验与序列化)
6. [依赖注入](#6-依赖注入)
7. [常用方法速查](#7-常用方法速查)
8. [教程：从零写一个书店](#8-教程从零写一个书店)
9. [数据库：同步与异步 SQLAlchemy](#9-数据库同步与异步-sqlalchemy)
10. [认证与安全](#10-认证与安全)
11. [中间件、异常处理与 lifespan](#11-中间件异常处理与-lifespan)
12. [后台任务、流式响应、WebSocket](#12-后台任务流式响应websocket)
13. [测试](#13-测试)
14. [工程实践](#14-工程实践)
15. [面试题与参考回答](#15-面试题与参考回答)
16. [常见坑](#16-常见坑)

---

## 1. 定位：FastAPI 是什么、适合什么

FastAPI 是基于 **类型注解** 的现代 API 框架，站在两个库的肩膀上：

| 组件 | 负责 |
|---|---|
| **Starlette** | ASGI 工具集：路由、请求 / 响应、中间件、WebSocket、后台任务、测试客户端 |
| **Pydantic** | 数据校验、序列化、JSON Schema |
| FastAPI 本身 | 把两者粘起来：从函数签名推断参数来源、**依赖注入**、自动生成 OpenAPI 文档 |

核心卖点：**写一次类型注解，同时得到参数解析、数据校验、编辑器补全、API 文档。**

| 维度 | Django | Flask | FastAPI |
|---|---|---|---|
| 协议 | WSGI / ASGI | WSGI | **ASGI** |
| 异步 | 渐进支持 | 有限 | **一等公民** |
| 校验 | Form / DRF | 无内置 | **Pydantic 内置** |
| API 文档 | 需扩展 | 需扩展 | **自动 `/docs` `/redoc`** |
| 依赖注入 | 无 | 无 | **内置 `Depends`** |
| ORM / Admin | 内置 | 无 | 无 |
| 典型场景 | 全栈站点、后台 | 小服务、传统 Web | 高并发 API、微服务、AI / LLM 服务 |

**什么时候选 FastAPI**：以 JSON API 为主；IO 密集、高并发；需要流式输出（LLM token 流）、WebSocket；需要给前端 / 第三方一份准确的接口文档；团队习惯类型注解。
**什么时候不选**：需要服务端渲染页面 + 后台管理 + 完整用户体系（Django 更省事）。

> **三框架对比 · 定位**
> - **相同**：FastAPI 与 Flask 都是装饰器路由、单文件起步；三者都能写 REST API。
> - **不同**：FastAPI 的核心差异是「**函数签名即接口契约**」——参数来源、类型、约束、返回结构全写在签名和 Pydantic 模型里，框架据此做校验和生成文档。Flask / Django 里这些信息散落在视图代码中，框架并不知道。

---

## 2. 安装与最小应用

```bash
python -m venv .venv && source .venv/bin/activate
pip install "fastapi[standard]"      # 带上 uvicorn、fastapi CLI、python-multipart 等
```

```python
# main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
```

```bash
fastapi dev main.py        # 开发：自动重载，默认 127.0.0.1:8000
fastapi run main.py        # 生产：监听 0.0.0.0，不重载
# 等价的底层命令：uvicorn main:app --reload
```

打开 `http://127.0.0.1:8000/docs` 就是自动生成、可直接调试的 Swagger UI；`/redoc` 是另一种风格；`/openapi.json` 是原始规范。

访问 `/items/abc` 会自动返回 **422**，并说明 `item_id` 不是合法整数——你一行校验代码都没写。

> **三框架对比 · 最小应用**
> 三者的「hello world」长度差不多，但 FastAPI 版本已经自带类型转换、参数校验和交互式文档；Flask 的 `<int:item_id>` 只做路由级转换，`q` 需要自己从 `request.args` 取；Django 需要整套项目骨架。

---

## 3. 请求生命周期与并发模型

### 3.1 生命周期

```text
ASGI 服务器（uvicorn）── scope / receive / send
  │
  ▼
Starlette 中间件栈
  │  ServerErrorMiddleware（兜底 500）
  │  → 用户中间件（后注册的在外层）
  │  → ExceptionMiddleware（处理 HTTPException 等）
  ▼
Router 匹配路径 + 方法
  │
  ▼
依赖解析（递归求值 Depends，同一请求内缓存）
  │  + 参数提取与 Pydantic 校验 ── 失败 → 422
  ▼
路径操作函数（async def 直接在事件循环跑；def 进线程池）
  │
  ▼
按 response_model 校验 / 过滤 / 序列化 → Response
  │
  ▼
yield 依赖的清理代码（finally 段）
  │
  ▼
中间件响应阶段 → 服务器 → 客户端
```

### 3.2 `async def` 还是 `def`？（最重要的一节）

| 写法 | 在哪执行 | 适合 |
|---|---|---|
| `async def` + 内部全是 `await` 异步 IO | 事件循环主线程 | 异步数据库驱动、httpx、aioredis 等 |
| `def` | AnyIO **线程池**（默认 40 个线程） | 同步库：传统 DB 驱动、requests、CPU 轻计算 |
| `async def` + 内部调用阻塞函数 | 事件循环主线程，**阻塞整个进程** | **绝对不要** |

本地实测（同一进程，4 个并发请求，每个请求内部「等待」0.5 秒）：

| 路由写法 | 4 个并发请求总耗时 | 解释 |
|---|---|---|
| `async def` 里 `time.sleep(0.5)` | **2.01 s** | 阻塞事件循环，请求被串行处理 |
| `def` 里 `time.sleep(0.5)` | 0.52 s | 线程池并行 |
| `async def` 里 `await asyncio.sleep(0.5)` | 0.50 s | 协程让出控制权，并发等待 |

结论：**不确定库是不是异步的，就写 `def`**；在 `async def` 里必须调用同步阻塞函数时，用 `await run_in_threadpool(func, ...)`（来自 `fastapi.concurrency`）或 `anyio.to_thread.run_sync`。CPU 密集任务两种都不合适，应交给进程池 / Celery。

依赖函数同理：`def` 依赖也会进线程池，`async def` 依赖在事件循环里跑。

> **三框架对比 · 并发模型**
> - **Django / Flask（WSGI）**：一个请求占一个线程 / 进程，并发数 ≈ worker 数 × 线程数，阻塞调用只影响自己那个线程。
> - **FastAPI（ASGI）**：单线程事件循环同时挂起大量请求，并发能力强，但一次阻塞就拖垮该进程上所有请求——这是 FastAPI 最大的心智负担。
> - **相同**：生产上三者都靠「多进程 worker」利用多核。

---

## 4. 参数声明：路径、查询、请求体、头

FastAPI 按规则推断参数来源：

| 参数形态 | 来源 |
|---|---|
| 名字出现在路径模板 `{book_id}` 中 | 路径参数 |
| 简单类型（int、str、bool、Enum…），不在路径中 | 查询参数 |
| Pydantic 模型 | JSON 请求体 |
| `Header()` / `Cookie()` / `Form()` / `File()` 标注 | 对应位置 |

推荐用 `Annotated` 写法，把类型和元数据放一起：

```python
from typing import Annotated
from fastapi import Cookie, File, Form, Header, Path, Query, UploadFile

@app.get("/books/{book_id}")
def get_book(
    book_id: Annotated[int, Path(ge=1)],
    fields: Annotated[list[str] | None, Query()] = None,      # ?fields=a&fields=b
    q: Annotated[str | None, Query(min_length=2, max_length=50)] = None,
    x_token: Annotated[str | None, Header()] = None,          # 自动对应 X-Token 头
    session_id: Annotated[str | None, Cookie()] = None,
): ...

@app.post("/upload")
async def upload(file: UploadFile, note: Annotated[str, Form()]):   # 需 python-multipart
    content = await file.read()
```

- 有默认值 = 可选；没有默认值 = 必填。
- 多个 Pydantic 模型参数 → 请求体变成 `{"book": {...}, "author": {...}}`；单个模型想也包一层用 `Body(embed=True)`。
- `UploadFile` 底层是临时文件（SpooledTemporaryFile），大文件不会全部读进内存。

> **三框架对比 · 取参数**
> - 查询参数：Django `request.GET.get("q")`，Flask `request.args.get("q")`，FastAPI 直接写 `q: str | None = None`。
> - JSON 请求体：Django `json.loads(request.body)`，Flask `request.get_json()`，FastAPI 写 `data: BookIn`，已校验、已转换类型。
> - 请求头：Django `request.headers["X-Token"]`，Flask `request.headers.get("X-Token")`，FastAPI `x_token: Annotated[str | None, Header()]`。

---

## 5. Pydantic：校验与序列化

### 5.1 入参模型与出参模型分离

```python
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookIn(BaseModel):                      # 客户端提交的
    title: str = Field(min_length=1, max_length=200)
    author: str
    price: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    stock: int = Field(default=0, ge=0)


class BookOut(BaseModel):                     # 返回给客户端的
    model_config = ConfigDict(from_attributes=True)   # 允许从 ORM 对象读取属性

    id: int
    title: str
    author: str
    price: Decimal
    stock: int

    @field_validator("author", mode="before")
    @classmethod
    def author_name(cls, value):
        return getattr(value, "name", value)  # ORM 的 Author 对象 → 名字字符串
```

为什么要分开：入参不该包含 `id`；出参不该包含 `password_hash` 之类的字段。常见再加一个 `BookUpdate`（所有字段可选，配合 `model_dump(exclude_unset=True)` 做 PATCH）。

### 5.2 `response_model` 的三个作用

1. **过滤**：返回值里多余的字段会被丢掉（实测返回 `{"name": ..., "password": ...}`，声明 `response_model=UserOut` 后客户端只收到 `name`）。
2. **校验**：返回数据不符合模型时报 500，及早发现 bug。
3. **文档**：在 OpenAPI 中描述响应结构。

也可以用返回类型注解 `def f() -> BookOut:` 达到同样效果；当实际返回 ORM 对象、类型对不上时用 `response_model=` 参数。

### 5.3 Pydantic v2 常用 API

| API | 说明 |
|---|---|
| `Model.model_validate(obj)` | 从 dict / 对象构造并校验 |
| `Model.model_validate_json(s)` | 直接从 JSON 字符串（更快） |
| `m.model_dump(exclude_unset=True)` | 转 dict，可只要客户端传了的字段 |
| `m.model_dump_json()` | 转 JSON 字符串 |
| `m.model_copy(update={...})` | 复制并修改 |
| `Field(gt=, ge=, min_length=, pattern=, alias=)` | 字段约束 |
| `@field_validator` / `@model_validator` | 单字段 / 跨字段校验 |
| `@computed_field` | 计算属性也参与序列化 |
| `ConfigDict(from_attributes=True, extra="forbid")` | 读 ORM 属性 / 禁止多余字段 |

v1 → v2 改名：`orm_mode` → `from_attributes`，`.dict()` → `.model_dump()`，`parse_obj` → `model_validate`，`@validator` → `@field_validator`。

> **三框架对比 · 校验**
> Pydantic `BaseModel` ≈ DRF `Serializer` ≈ Marshmallow `Schema`。差异在于：Pydantic 用类型注解声明，FastAPI 能 **自动** 把它接到请求解析、422 错误和 OpenAPI 上；DRF 要在视图里调 `is_valid()`；Flask 什么都不内置。

---

## 6. 依赖注入

依赖就是「一个可调用对象，FastAPI 在调用路由前先调用它，把返回值注入参数」。用来共享：数据库会话、当前用户、配置、分页参数、权限检查等。

### 6.1 基本形态

```python
from typing import Annotated
from fastapi import Depends, Header, HTTPException

def pagination(skip: int = 0, limit: int = 20) -> dict:     # 依赖本身也能声明查询参数
    return {"skip": skip, "limit": limit}

Page = Annotated[dict, Depends(pagination)]

@app.get("/books/")
def list_books(page: Page): ...
```

### 6.2 `yield` 依赖：资源获取与释放

```python
def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session              # yield 之前：请求前执行；之后：响应后清理

SessionDep = Annotated[Session, Depends(get_session)]
```

### 6.3 子依赖与缓存

```python
def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep): ...
def require_admin(user: Annotated[User, Depends(get_current_user)]): ...
```

FastAPI 会构建一张依赖图递归求值。**同一个请求里，同一个依赖只执行一次**（`use_cache=True` 默认）：实测一个路由直接依赖 `get_db`、它的子依赖也依赖 `get_db`，`get_db` 只被调用一次，并且在请求结束后清理。要强制每次都执行用 `Depends(dep, use_cache=False)`。**跨请求不缓存**。

### 6.4 作用范围

```python
@router.post("/", dependencies=[Depends(require_token)])     # 只要副作用（校验），不要返回值
router = APIRouter(dependencies=[Depends(require_token)])    # 整个路由组
app = FastAPI(dependencies=[Depends(verify_key)])            # 全局
```

### 6.5 测试时替换

```python
app.dependency_overrides[get_session] = override_session
app.dependency_overrides[get_settings] = lambda: Settings(api_token="t")
```

> **三框架对比 · 依赖注入**
> - Django / Flask 没有内置 DI。Flask 用 `g` + `before_request` 共享请求级对象（隐式全局）；Django 靠中间件往 `request` 上挂属性（如 `request.user`）。
> - FastAPI 的依赖 **显式出现在函数签名里**：一眼看出这个接口需要什么，测试时一行 `dependency_overrides` 就能替换。这是它在大型项目中可维护性好的关键原因。
> - `yield` 依赖 ≈ Flask 的「`before_request` 取资源 + `teardown_request` 释放」合并成一个函数。

---

## 7. 常用方法速查

### 7.1 应用与路由

| 名称 | 说明 |
|---|---|
| `FastAPI(title=, lifespan=, dependencies=)` | 创建应用 |
| `@app.get/post/put/patch/delete(path, ...)` | 路由 |
| 路由参数：`response_model` `status_code` `tags` `summary` `dependencies` `responses` `deprecated` | 控制行为与文档 |
| `APIRouter(prefix=, tags=, dependencies=)` | 路由分组 |
| `app.include_router(router, prefix=...)` | 挂载 |
| `app.mount("/static", StaticFiles(directory="static"))` | 挂载子应用 / 静态文件 |
| `app.state` / `request.app.state` | 应用级共享对象 |
| `app.dependency_overrides` | 依赖替换 |

### 7.2 参数与请求

| 名称 | 说明 |
|---|---|
| `Path` `Query` `Body` `Header` `Cookie` `Form` `File` | 参数来源与约束 |
| `UploadFile` | 上传文件（`await file.read()`） |
| `Request` | 原始请求（`request.client.host`、`request.headers`） |
| `Depends` / `Security` | 依赖 / 带 scope 的安全依赖 |
| `BackgroundTasks` | 后台任务 |

### 7.3 响应与异常

| 名称 | 说明 |
|---|---|
| `JSONResponse` `HTMLResponse` `PlainTextResponse` `RedirectResponse` `FileResponse` | 各类响应 |
| `StreamingResponse` | 流式 |
| `fastapi.sse.EventSourceResponse` / `ServerSentEvent` | 原生 SSE |
| `Response(status_code=204)` | 空响应 |
| `HTTPException(status_code, detail, headers)` | 抛 HTTP 错误 |
| `@app.exception_handler(Exc)` | 自定义异常处理 |
| `RequestValidationError` | 422 校验错误的异常类 |
| `status.HTTP_201_CREATED` 等 | 状态码常量 |
| `jsonable_encoder(obj)` | 转成可 JSON 序列化的结构 |

### 7.4 命令

| 命令 | 说明 |
|---|---|
| `fastapi dev main.py` | 开发（自动重载） |
| `fastapi run main.py --workers 4` | 生产 |
| `uvicorn app.main:app --reload` | 直接用 uvicorn |

---

## 8. 教程：从零写一个书店

目标：图书 CRUD + 搜索 + 购买扣库存（防超卖）+ Token 鉴权 + 后台通知 + 请求耗时头 + 自动文档。

### 8.1 目录

```text
fastsite/
├── app/
│   ├── config.py     # Settings（pydantic-settings）
│   ├── db.py         # engine、会话、模型、get_session 依赖
│   ├── schemas.py    # Pydantic 入参 / 出参
│   ├── deps.py       # 依赖：会话、配置、鉴权
│   ├── books.py      # books 路由
│   └── main.py       # 应用、lifespan、中间件
└── test_app.py
```

### 8.2 配置（敏感项从环境变量读）

```python
# app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BOOKSHOP_", env_file=".env")

    database_url: str = "sqlite:///./bookshop.db"
    api_token: str = "dev-only-token"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- 字段自动从环境变量 `BOOKSHOP_DATABASE_URL`、`BOOKSHOP_API_TOKEN` 读取，并做类型校验。
- `dev-only-token` 只是本地占位；生产必须通过环境变量 / 密钥管理服务注入，`.env` 不进 git。
- `@lru_cache` 让配置只解析一次；通过依赖注入使用，测试时可以 override。

### 8.3 数据库与模型

```python
# app/db.py
from collections.abc import Iterator
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from .config import get_settings

engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "author"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Book(Base):
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    stock: Mapped[int] = mapped_column(default=0)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author: Mapped[Author] = relationship(back_populates="books", lazy="joined")


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

- `check_same_thread=False` 是 SQLite 专用：`def` 路由在线程池里执行，会话可能跨线程。
- `expire_on_commit=False`：commit 后对象属性不过期，返回给 `response_model` 序列化时不会再触发查询。
- `lazy="joined"`：加载 Book 时 JOIN 取回 author，序列化 `BookOut.author` 时不会 N+1。

### 8.4 依赖

```python
# app/deps.py
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import get_session

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def require_token(settings: SettingsDep, x_token: Annotated[str | None, Header()] = None) -> None:
    if x_token != settings.api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")
```

示例用简单的共享 Token 演示依赖注入；真实项目用 OAuth2 + JWT（见第 10 节），比较密钥时用 `secrets.compare_digest` 防时序攻击。

### 8.5 路由

```python
# app/books.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, update

from .db import Author, Book
from .deps import SessionDep, require_token
from .schemas import BookIn, BookOut

router = APIRouter(prefix="/books", tags=["books"])
notifications: list[str] = []


def notify(title: str) -> None:
    notifications.append(f"new book: {title}")


@router.get("/", response_model=list[BookOut])
def list_books(session: SessionDep, q: str | None = None, limit: int = 20):
    stmt = select(Book).order_by(Book.id).limit(limit)
    if q:
        stmt = stmt.where(Book.title.ilike(f"%{q}%"))
    return session.scalars(stmt).all()


@router.post(
    "/",
    response_model=BookOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_token)],
)
def create_book(data: BookIn, session: SessionDep, background: BackgroundTasks):
    author = session.scalar(select(Author).where(Author.name == data.author)) or Author(name=data.author)
    book = Book(title=data.title, author=author, price=data.price, stock=data.stock)
    session.add(book)
    session.commit()
    background.add_task(notify, book.title)
    return book


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, session: SessionDep):
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    return book


@router.post("/{book_id}/buy")
def buy(book_id: int, session: SessionDep):
    result = session.execute(
        update(Book).where(Book.id == book_id, Book.stock > 0).values(stock=Book.stock - 1)
    )
    session.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=409, detail="sold out")
    return {"ok": True}
```

注意：这里全部用 `def`，因为用的是同步 SQLAlchemy 会话——同步 IO 放在 `async def` 里会阻塞事件循环。

### 8.6 应用入口

```python
# app/main.py
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from . import books
from .db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)       # 演示用；生产用 Alembic 迁移
    yield
    engine.dispose()


app = FastAPI(title="Bookshop", lifespan=lifespan)
app.include_router(books.router)


@app.middleware("http")
async def add_elapsed(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Elapsed-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}
```

```bash
fastapi dev app/main.py
curl -X POST localhost:8000/books/ -H "X-Token: dev-only-token" \
     -H "Content-Type: application/json" \
     -d '{"title":"FastAPI","author":"Ada","price":"25.00","stock":1}'
```

实测行为：

| 请求 | 结果 |
|---|---|
| 正确创建 | 201，`{"id":1,"title":"FastAPI","author":"Ada","price":"25.00","stock":1}`，后台通知已执行 |
| `title=""`、`price=0` | 422，`loc` 精确指出 `body.title`、`body.price` |
| 不带 `X-Token` | 401 |
| `GET /books/99` | 404，`{"detail":"book not found"}` |
| `GET /books/abc` | 422（路径参数类型不对） |
| 库存 1 连买两次 | 200 → 409 |

> **三框架对比 · 同一个书店**
> - 输入校验：Flask 版手写 `missing` 检查返回 400；Django 原生版直接 `json.loads` 不校验（DRF 版才有）；FastAPI 声明 `BookIn` 即自动 422，错误定位到字段。
> - 鉴权：Django 用 DRF `permission_classes`；Flask 常用装饰器或 `before_request`；FastAPI 用 `dependencies=[Depends(require_token)]`。
> - 错误格式：三份示例都统一成 `{"detail": ...}`，这是 FastAPI 的默认格式。

---

## 9. 数据库：同步与异步 SQLAlchemy

### 9.1 同步（上面教程的写法）

路由写 `def`，依赖 `yield` 一个 `Session`。简单可靠，线程池默认 40 个线程，对多数业务足够。

### 9.2 异步

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = create_async_engine("postgresql+asyncpg://...", pool_size=10, max_overflow=20)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/{book_id}")
async def get_book(book_id: int, session: Annotated[AsyncSession, Depends(get_session)]):
    book = await session.get(Book, book_id)
```

异步模式的要点：

- **不能懒加载**：访问未加载的关系属性会报错（`MissingGreenlet`），必须用 `selectinload` / `joinedload` 预加载，或 `await session.refresh(obj, ["author"])`。
- 驱动要用异步的：PostgreSQL `asyncpg` / `psycopg`（v3），MySQL `aiomysql` / `asyncmy`，SQLite `aiosqlite`。
- 数据库连接池大小要和 worker 数一起算，避免打满数据库最大连接数。

### 9.3 迁移

FastAPI 不管迁移，用 **Alembic**：`alembic init`，`env.py` 里设置 `target_metadata = Base.metadata`，然后 `alembic revision --autogenerate -m "..."` + `alembic upgrade head`。

### 9.4 SQLModel

SQLModel（FastAPI 作者出品）让一个类同时是 SQLAlchemy 模型和 Pydantic 模型，减少重复定义；复杂场景仍建议 ORM 模型与 API Schema 分离。

> **三框架对比 · 数据库**
> - Django：ORM、迁移、连接管理一体化，`Book.objects.filter()` 开箱即用。
> - Flask：Flask-SQLAlchemy 把 session 绑在应用上下文上，Flask-Migrate 管迁移。
> - FastAPI：直接用 SQLAlchemy + Alembic，会话通过 `yield` 依赖显式注入；可以选同步或完全异步链路。

---

## 10. 认证与安全

### 10.1 OAuth2 Password + JWT（最常见的 API 认证）

```python
import jwt                                   # PyJWT
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")   # 文档里会出现 Authorize 按钮

@app.post("/auth/token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], settings: SettingsDep):
    user = authenticate(form.username, form.password)          # 校验密码哈希
    if not user:
        raise HTTPException(401, "bad credentials", headers={"WWW-Authenticate": "Bearer"})
    payload = {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=30)}
    return {"access_token": jwt.encode(payload, settings.jwt_secret, algorithm="HS256"),
            "token_type": "bearer"}

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], settings: SettingsDep) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})
    return load_user(payload["sub"])

CurrentUser = Annotated[User, Depends(get_current_user)]
```

要点：

- `jwt_secret` 从环境变量读（`Settings` 字段），**不能写在代码里**。
- `jwt.decode` 必须显式指定 `algorithms`，防止算法混淆攻击。
- 密码用 Argon2 / bcrypt 哈希（如 `pwdlib`），绝不存明文、不用 MD5 / SHA1。
- 其他工具：`HTTPBearer`、`APIKeyHeader`、`Security(..., scopes=[...])` 做细粒度权限。

### 10.2 其他

| 需求 | 方案 |
|---|---|
| CORS | `app.add_middleware(CORSMiddleware, allow_origins=[...])`，生产不要 `*` 配 `allow_credentials=True` |
| 限流 | slowapi，或在网关层做 |
| HTTPS / 安全头 | 反向代理层处理；`TrustedHostMiddleware` 限制 Host |
| 生产关闭文档 | `FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` |

> **三框架对比 · 认证**
> Django 自带 User 模型、Session 认证、权限系统；Flask 用 Flask-Login / Flask-JWT-Extended；FastAPI 提供 `fastapi.security` 工具类（负责从请求里取凭据、生成文档），用户存储和校验逻辑自己写，再用依赖注入组合成 `CurrentUser`。

---

## 11. 中间件、异常处理与 lifespan

### 11.1 中间件

```python
@app.middleware("http")
async def add_elapsed(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)          # 之前：请求阶段；之后：响应阶段
    response.headers["X-Elapsed-Ms"] = ...
    return response

app.add_middleware(CORSMiddleware, allow_origins=["https://example.com"], allow_methods=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**执行顺序**：后注册的在外层。实测先注册 `first` 再注册 `second`，请求进来顺序是 `second → first → 路由 → first → second`。

`@app.middleware("http")` 底层是 Starlette 的 `BaseHTTPMiddleware`，简单好用；对性能极敏感或需要处理流式响应时，写纯 ASGI 中间件（`async def __call__(self, scope, receive, send)`）开销更小。

### 11.2 异常处理

```python
class OutOfStock(Exception):
    def __init__(self, book_id: int):
        self.book_id = book_id

@app.exception_handler(OutOfStock)
async def out_of_stock_handler(request: Request, exc: OutOfStock):
    return JSONResponse(status_code=409, content={"detail": f"book {exc.book_id} sold out"})

@app.exception_handler(RequestValidationError)     # 自定义 422 格式
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"errors": exc.errors()})
```

业务层抛领域异常，在边界统一转换成 HTTP 响应，service 层就不需要依赖 FastAPI。

### 11.3 lifespan：启动与关闭

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient()          # 启动：建连接池、加载模型
    yield
    await app.state.http.aclose()                 # 关闭：统一释放

app = FastAPI(lifespan=lifespan)
```

旧的 `@app.on_event("startup")` / `("shutdown")` 已弃用。昂贵资源（连接池、ML 模型、HTTP 客户端）应在 lifespan 里建一次、全程复用，而不是每个请求新建。

> **三框架对比 · 启动钩子**
> - Django：`AppConfig.ready()`（注意不要在里面查数据库）。
> - Flask：没有统一的启动钩子，通常在应用工厂 `create_app` 里初始化。
> - FastAPI：lifespan，一个函数同时写启动和关闭逻辑，不容易漏掉清理。

---

## 12. 后台任务、流式响应、WebSocket

### 12.1 BackgroundTasks

```python
def create_book(data: BookIn, background: BackgroundTasks):
    ...
    background.add_task(notify, book.title)      # 响应发出后执行
    return book
```

- 在 **响应发送之后、同一进程内** 执行，客户端不用等。
- 适合发邮件、写审计日志、清缓存这类轻量、丢了也能接受的任务。
- 进程重启任务就没了，没有重试、没有持久化；重任务 / 需要可靠性用 Celery、arq、Dramatiq。

### 12.2 流式响应与 SSE

```python
from fastapi.responses import StreamingResponse

@app.get("/download")
def download():
    def chunks():
        for i in range(3):
            yield f"line {i}\n"
    return StreamingResponse(chunks(), media_type="text/plain")
```

FastAPI 当前版本内置了 SSE 支持：

```python
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.get("/chat", response_class=EventSourceResponse)
async def chat():
    for tok in ["Hel", "lo"]:
        yield {"token": tok}                               # 自动 JSON 序列化成 data: ...
    yield ServerSentEvent(data="[DONE]", event="end")      # 可指定 event / id / retry
```

实测输出：`data: {"token": "Hel"}\n\ndata: {"token": "lo"}\n\nevent: end\ndata: "[DONE]"\n\n`。注意 `data` 一律 JSON 序列化，纯字符串也会带引号。

老版本或需要更细控制时，可以用 `StreamingResponse(gen(), media_type="text/event-stream")` 自己拼 `data: ...\n\n`。LLM token 流用 SSE 而非 WebSocket，是因为它是服务端单向推送、基于普通 HTTP、浏览器 `EventSource` 原生支持且自动重连。

### 12.3 WebSocket

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"echo: {msg}")
    except WebSocketDisconnect:
        pass
```

多实例部署时，广播需要借助 Redis Pub/Sub 等外部组件。

> **三框架对比 · 流式与长连接**
> - FastAPI：ASGI 原生支持，流式 / SSE / WebSocket 都不占线程。
> - Flask：可以返回生成器做流式，但每个流占一个 worker 线程直到结束；WebSocket 需要 flask-sock 或换 Quart。
> - Django：`StreamingHttpResponse` 可流式；WebSocket 需要 Django Channels。

---

## 13. 测试

```python
# test_app.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import books
from app.config import Settings, get_settings
from app.db import Base, get_session
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, expire_on_commit=False)


def override_session():
    with TestSession() as session:
        yield session


@pytest.fixture
def client():
    Base.metadata.create_all(engine)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = lambda: Settings(api_token="t")
    with TestClient(app) as c:                 # with 块会触发 lifespan
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


AUTH = {"X-Token": "t"}


def make(client, **kw):
    body = {"title": "FastAPI", "author": "Ada", "price": "25.00", "stock": 1} | kw
    return client.post("/books/", json=body, headers=AUTH)


def test_create_list_and_background(client):
    books.notifications.clear()
    resp = make(client)
    assert resp.status_code == 201
    assert resp.json() == {"id": 1, "title": "FastAPI", "author": "Ada", "price": "25.00", "stock": 1}
    assert books.notifications == ["new book: FastAPI"]


def test_validation_422(client):
    resp = client.post("/books/", json={"title": "", "author": "Ada", "price": "0"}, headers=AUTH)
    assert resp.status_code == 422
    locs = sorted(tuple(e["loc"]) for e in resp.json()["detail"])
    assert locs == [("body", "price"), ("body", "title")]


def test_auth_and_404(client):
    assert client.post("/books/", json={"title": "x", "author": "a", "price": "1"}).status_code == 401
    assert client.get("/books/99").json() == {"detail": "book not found"}
    assert client.get("/books/abc").status_code == 422
```

- `StaticPool` + `sqlite://`：内存数据库在多个连接间共享，否则每个连接都是一个空库。
- `dependency_overrides` 一行替换数据库会话和配置，不需要 monkeypatch。
- `TestClient` 在后台线程跑事件循环，测试函数本身可以是普通 `def`。
- 需要在测试里 `await`（例如测异步依赖）时，用 `httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")` + `pytest-anyio` / `pytest-asyncio`。注意 ASGITransport 不会触发 lifespan。
- 新版 Starlette 在使用 `TestClient` 时会提示 httpx 用法已弃用、建议改装 `httpx2`，目前只是警告，不影响结果。

本地验证结果：`pytest` → **5 passed**（OpenAPI 与 `/docs` 也在测试中验证）。

> **三框架对比 · 测试**
> - **相同**：三者的测试客户端都不启动真实服务器，直接调用应用对象。
> - **不同**：Django 的数据库隔离最省心（自动建库 + 回滚）；FastAPI 的依赖替换最省心（`dependency_overrides`）；Flask 介于两者之间，靠应用工厂传测试配置。

---

## 14. 工程实践

### 14.1 推荐结构（按领域拆分）

```text
project/
├── app/
│   ├── main.py              # create app、lifespan、中间件、挂路由
│   ├── core/
│   │   ├── config.py        # Settings
│   │   ├── security.py      # 密码哈希、JWT
│   │   └── db.py            # engine、session 依赖
│   ├── books/
│   │   ├── router.py        # 只做 HTTP 适配
│   │   ├── schemas.py       # Pydantic
│   │   ├── models.py        # ORM
│   │   ├── service.py       # 业务逻辑（不 import fastapi）
│   │   └── deps.py
│   └── users/ ...
├── alembic/
├── tests/
└── pyproject.toml
```

- **router 薄、service 厚**：service 不依赖 FastAPI，抛领域异常，由异常处理器统一转 HTTP。
- **Schema 与 ORM 模型分离**：入参 / 出参 / 数据库三种结构的演进节奏不同。
- 依赖用 `Annotated` 别名（`SessionDep`、`CurrentUser`）减少重复。

### 14.2 部署

```bash
fastapi run app/main.py --workers 4
# 或
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
# 或 gunicorn 管理进程（需 pip install uvicorn-worker）
gunicorn app.main:app -k uvicorn_worker.UvicornWorker -w 4
```

- Worker 数从 CPU 核数起步再压测调整；容器 / K8s 环境里常见做法是每个容器 1 个进程，靠副本数横向扩展。
- 在反向代理后运行时开启 `--proxy-headers` 并配置 `--forwarded-allow-ips`，否则拿不到真实客户端 IP 和协议。
- 线程池大小：同步路由多、阻塞时间长时，线程池（默认 40）可能成为瓶颈，可在 lifespan 中通过 `anyio.to_thread.current_default_thread_limiter().total_tokens = N` 调整，但更根本的办法是改用异步驱动。

### 14.3 性能要点

| 要点 | 说明 |
|---|---|
| 不阻塞事件循环 | 同步调用放 `def` 路由或 `run_in_threadpool` |
| 复用连接 | 数据库连接池、`httpx.AsyncClient` 在 lifespan 中创建 |
| 避免 N+1 | `selectinload` / `joinedload` |
| 响应序列化 | 声明 `response_model` 或返回类型，由 Pydantic（Rust 内核）序列化 |
| 缓存 | 单进程用 cachetools；多 worker 用 Redis。Peewee / SQLAlchemy / Memcached 的取舍见 [常用第三方库](./libraries.md) |

### 14.4 可观测性

结构化日志、`/health` 健康检查、Prometheus 指标（prometheus-fastapi-instrumentator）、OpenTelemetry 链路追踪、Sentry 异常监控。

> **三框架对比 · 工程化**
> - Django：框架定好了分层（App / models / views / admin），团队上手统一。
> - Flask：完全自定，靠团队规范。
> - FastAPI：框架提供 DI 和 Schema 两个「骨架」，按领域拆 router / schemas / service 是社区共识，`dependency_overrides` 让分层后的测试成本很低。

---

## 15. 面试题与参考回答

**Q1：FastAPI 为什么快？**
一是基于 ASGI 和 Starlette，异步 IO 让单进程可以同时处理大量等待 IO 的请求；二是 Pydantic v2 核心用 Rust 实现，校验和序列化开销小；三是 uvicorn 使用 uvloop 和 httptools 等高性能组件。但「快」主要体现在 IO 密集场景，CPU 密集任务并不会因为用了 FastAPI 而变快，而且一旦在 `async def` 里写了阻塞代码，性能反而会比同步框架更差。

**Q2：`async def` 和 `def` 路由有什么区别？怎么选？**
`async def` 路由直接在事件循环中执行，适合内部全是 `await` 异步 IO 的场景；`def` 路由被放到 AnyIO 线程池（默认 40 个线程）执行，适合调用同步阻塞库。如果在 `async def` 里调用了 `time.sleep`、同步数据库驱动、`requests` 等阻塞操作，会卡住整个事件循环，所有请求都被串行化——实测 4 个并发请求从 0.5 秒变成 2 秒。原则：库是异步的就用 `async def`，不确定就用 `def`。

**Q3：讲讲 FastAPI 的依赖注入。**
依赖是一个可调用对象，在函数签名中用 `Depends` 声明，FastAPI 在调用路由前先递归求值整张依赖图，把结果注入参数。依赖可以有自己的参数（查询参数、头、其他依赖）。带 `yield` 的依赖在 yield 前获取资源、yield 后释放，常用于数据库会话。同一请求内同一依赖默认只执行一次并复用结果（`use_cache=True`），跨请求不共享。测试时通过 `app.dependency_overrides` 替换。它的价值是让依赖显式、可组合、可替换。

**Q4：Pydantic 在 FastAPI 中起什么作用？`response_model` 有什么用？**
入参方面，Pydantic 模型定义请求体结构和约束，FastAPI 自动解析 JSON、校验、类型转换，失败返回 422 并指出字段位置。出参方面，`response_model` 负责过滤多余字段（比如防止把密码哈希返回出去）、校验返回值结构，并生成 OpenAPI 文档。同时这些模型还驱动了自动文档和编辑器补全。

**Q5：422 和 400 有什么区别？**
FastAPI 中 422 Unprocessable Entity 表示请求格式正确但内容校验失败，由 Pydantic 校验自动触发，返回详细的字段错误列表。400 Bad Request 通常由业务代码主动抛出，表示业务层面的请求错误。可以通过注册 `RequestValidationError` 的异常处理器自定义 422 的格式。

**Q6：BackgroundTasks 和 Celery 有什么区别？**
BackgroundTasks 在响应发出后、在同一个进程内执行，零配置，但没有持久化、重试和分布式能力，进程重启任务就丢失，而且耗时任务会占用当前 worker 的资源。Celery 是独立的分布式任务队列，有 broker、持久化、重试、定时、横向扩展。轻量、可丢失的任务用 BackgroundTasks，重要或耗时的任务用 Celery。

**Q7：lifespan 是什么？为什么取代 on_event？**
lifespan 是一个异步上下文管理器，yield 之前的代码在应用启动时执行一次，之后的代码在关闭时执行一次，用来管理连接池、HTTP 客户端、模型等昂贵资源。它取代 `on_event` 是因为把启动和关闭逻辑写在一个函数里，资源的创建和释放成对出现，不易遗漏，也能用局部变量在两段之间共享状态。

**Q8：中间件和依赖都能做鉴权，怎么选？**
中间件作用于所有请求（包括 404、静态文件），拿到的是原始请求和响应，适合日志、耗时、CORS、全局限流这类与具体路由无关的横切逻辑。依赖作用于具体路由或路由组，能拿到解析后的参数，能参与 OpenAPI 文档（例如显示需要 Bearer Token），也能被测试替换。鉴权通常用依赖，因为不同接口权限不同，且需要把当前用户传给路由。

**Q9：FastAPI 如何处理大量并发连接？如何扩展？**
单进程靠事件循环处理并发 IO；多核靠多个 worker 进程（`--workers` 或 gunicorn + uvicorn worker）；多机靠负载均衡和容器副本。要注意数据库连接池总数 = 每进程池大小 × 进程数 × 副本数，不能超过数据库上限；状态（session、WebSocket 广播）要外置到 Redis。

**Q10：如何在 FastAPI 中做流式输出（比如 LLM）？**
用 `StreamingResponse` 包装一个生成器 / 异步生成器边生成边发送；对浏览器推送场景用 SSE，当前版本可以直接声明 `response_class=EventSourceResponse` 然后 `yield` 数据。SSE 基于 HTTP、单向、自动重连，正适合 token 流；需要双向实时通信才用 WebSocket。

**Q11：FastAPI 与 Flask、Django 的核心区别？**
FastAPI 是 ASGI 异步框架，以类型注解为核心，内置校验、依赖注入和自动文档，专注 API。Flask 是 WSGI 同步微框架，核心极简，功能靠扩展。Django 是全栈框架，内置 ORM、Admin、认证、模板，适合完整 Web 应用。选型上：纯 API、高并发、流式选 FastAPI；需要后台和完整业务体系选 Django；轻量定制或维护传统 Web 选 Flask。

**Q12：使用异步 SQLAlchemy 要注意什么？**
必须用异步驱动；不能隐式懒加载关系属性，要预加载或显式 refresh；会话不能在多个并发任务间共享；`expire_on_commit=False` 避免提交后访问属性触发 IO；连接池大小要和并发量、进程数匹配。

---

## 16. 常见坑

| 坑 | 正确做法 |
|---|---|
| `async def` 里调用同步阻塞库 | 改 `def`，或 `run_in_threadpool` |
| 每个请求新建 `httpx.AsyncClient` / 数据库引擎 | 在 lifespan 中创建一次 |
| 返回 ORM 对象没声明 `response_model`，泄露敏感字段 | 用出参模型过滤 |
| 继续用 `@app.on_event` | 改 lifespan |
| 异步 ORM 访问关系属性报错 | `selectinload` 预加载 |
| 测试用 `sqlite://` 每次连接都是空库 | `StaticPool` |
| 用 `BackgroundTasks` 跑长任务 / 必须成功的任务 | Celery / arq |
| 生产环境暴露 `/docs` 和 `/openapi.json` | 按需关闭或加鉴权 |
| CORS `allow_origins=["*"]` 配合 `allow_credentials=True` | 显式列出可信源 |
| 密钥 / Token 写死在代码里 | `pydantic-settings` 从环境变量读 |
| `jwt.decode` 不指定 `algorithms` | 显式指定，防算法混淆 |
| 以为 `fastapi dev` 可以上生产 | 用 `fastapi run` / uvicorn 多 worker |
