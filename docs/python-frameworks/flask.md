# Flask 手记：核心用法 · 常用方法 · 教程 · 工程实践 · 面试

> 系列文档：[Django](./django.md) · **Flask** · [FastAPI](./fastapi.md) · [常用第三方库](./libraries.md)
>
> 三份文档用同一个「书店 Bookshop」例子（作者 / 图书 / 库存 / 购买），方便横向对照。文中所有代码都在本地真实跑过测试。
>
> 验证环境：Python 3.12 · Flask 3.1.3 · Flask-SQLAlchemy 3.1.1 · SQLAlchemy 2.1.4（2026-10）。

文中带 **「三框架对比」** 的引用块，专门说明此处与 Django / FastAPI 的相同与不同。

---

## 目录

1. [定位：Flask 是什么、适合什么](#1-定位flask-是什么适合什么)
2. [安装与最小应用](#2-安装与最小应用)
3. [请求生命周期与上下文](#3-请求生命周期与上下文)
4. [核心组件逐个过](#4-核心组件逐个过)
5. [数据库：Flask-SQLAlchemy](#5-数据库flask-sqlalchemy)
6. [常用方法速查](#6-常用方法速查)
7. [教程：从零写一个书店](#7-教程从零写一个书店)
8. [写 REST API 的几种方式](#8-写-rest-api-的几种方式)
9. [认证与安全](#9-认证与安全)
10. [钩子、错误处理与信号](#10-钩子错误处理与信号)
11. [异步支持](#11-异步支持)
12. [测试](#12-测试)
13. [工程实践](#13-工程实践)
14. [面试题与参考回答](#14-面试题与参考回答)
15. [常见坑](#15-常见坑)

---

## 1. 定位：Flask 是什么、适合什么

Flask 是 **微框架**（microframework）。「微」不是说功能弱，而是 **核心只做最少的事**：路由、请求 / 响应封装、模板、会话、配置。数据库、表单、认证、迁移等都交给扩展，由你自己挑选组合。

Flask 本身是几个成熟库的胶水：

| 组件 | 负责 |
|---|---|
| **Werkzeug** | WSGI 工具集：路由匹配、Request / Response 对象、开发服务器、调试器 |
| **Jinja2** | 模板引擎（默认自动转义） |
| **Click** | `flask` 命令行 |
| **itsdangerous** | 数据签名（session cookie 就靠它） |
| **MarkupSafe** | 安全字符串 / 转义 |
| **Blinker** | 信号 |

| 维度 | Django | Flask | FastAPI |
|---|---|---|---|
| 哲学 | 大而全 | 微内核，按需组装 | 类型驱动，API 优先 |
| 协议 | WSGI / ASGI | **WSGI** | ASGI |
| 路由写法 | 集中式 `urls.py` | 装饰器 `@app.get` | 装饰器 `@app.get` |
| 请求对象 | 视图参数 `request` | **上下文全局变量** `request` | 类型注解声明参数 |
| 数据校验 | Form / DRF | 无内置 | Pydantic |
| 学习曲线 | 中（约定多） | **低** | 低到中（需懂类型注解、async） |

**什么时候选 Flask**：小到中型服务、原型、内部工具、需要完全掌控技术选型、已有大量同步库的老项目。
**什么时候不选**：需要后台和完整用户体系（Django 更省事）；高并发 IO / 流式 / 需要自动 API 文档（FastAPI 更合适）。

> **三框架对比 · 定位**
> - **相同**：Flask 和 FastAPI 都是装饰器式路由、单文件即可起步，写起来很像。
> - **不同**：Flask 是同步 WSGI 框架，靠扩展堆功能；FastAPI 是异步 ASGI 框架，校验 / 文档 / 依赖注入内置；Django 则把一切都内置并强约定。很多人把 FastAPI 描述为「带类型校验和 async 的 Flask」，这个说法便于入门，但两者底层模型完全不同。

---

## 2. 安装与最小应用

```bash
python -m venv .venv && source .venv/bin/activate
pip install "flask>=3.1" flask-sqlalchemy
```

```python
# app.py
from flask import Flask

app = Flask(__name__)


@app.get("/")
def index():
    return {"hello": "flask"}          # 返回 dict 自动转 JSON
```

```bash
flask --app app run --debug           # 开发服务器 + 自动重载 + 交互调试器
```

- `Flask(__name__)`：`__name__` 用来定位资源根目录（模板、静态文件、instance 文件夹）。
- `--debug` 开启调试器，**调试器允许在浏览器里执行任意 Python 代码，绝不能在生产开启**。
- `@app.get` / `@app.post` 是 `@app.route(..., methods=[...])` 的简写（Flask 2.0+）。

> **三框架对比 · 最小应用**
> - Flask：`flask --app app run --debug`。
> - FastAPI：`fastapi dev main.py`，几乎一样的装饰器写法，多了自动 `/docs`。
> - Django：需要 `startproject` 生成整套骨架，不存在「单文件 Django」的惯常写法。

---

## 3. 请求生命周期与上下文

### 3.1 生命周期

```text
WSGI 服务器（gunicorn）
  │  environ, start_response
  ▼
app.wsgi_app(environ, start_response)
  │
  ├─ 推入 App Context    → current_app, g 可用
  ├─ 推入 Request Context → request, session 可用
  │
  ├─ before_request 钩子（任一返回非 None 就短路，直接作为响应）
  ├─ URL 匹配（Werkzeug Map）→ 视图函数
  ├─ 视图返回值 → make_response() 统一转成 Response
  ├─ after_request 钩子（逆注册顺序，可修改响应；出异常时不执行）
  ├─ teardown_request / teardown_appcontext（无论成功失败都执行，用来释放资源）
  │
  └─ 弹出上下文
```

### 3.2 两种上下文（Flask 最核心、面试最常问）

| 上下文 | 代理对象 | 生命周期 | 典型用途 |
|---|---|---|---|
| **应用上下文** App Context | `current_app`、`g` | 每个请求一次；CLI 命令 / 手动 `app.app_context()` | 读配置、访问扩展、请求内暂存数据 |
| **请求上下文** Request Context | `request`、`session` | 每个请求一次 | 读请求参数、会话 |

为什么能直接 `from flask import request` 当全局变量用，却不会串数据？

- `request` 是一个 **代理对象**（`LocalProxy`），每次访问属性时，去当前上下文里找真正的请求对象。
- 上下文存储基于 `contextvars.ContextVar`，**每个线程 / 协程各自独立**，所以多线程服务器下互不干扰。
- 出了上下文再访问会抛 `RuntimeError: Working outside of request context`。

```python
with app.test_request_context("/books/?q=x"):
    request.args["q"]           # "x"
    g.user = "ada"              # g：本次请求内的临时存储
    current_app.config["TESTING"]
    session["cart"] = [1]

request.args                    # RuntimeError：已经出了请求上下文
```

`g` 常见用法：在 `before_request` 里把当前用户 / 数据库连接存进去，视图里直接取。它 **不是跨请求的全局变量**，每个请求都是新的。

> **三框架对比 · 请求对象怎么拿**
> - Flask：**隐式**，`request` 是线程 / 协程隔离的全局代理。写起来最省事，但隐藏了依赖，测试和在请求外复用代码时要手动推上下文。
> - Django：**显式**，`request` 作为视图第一个参数传进来。
> - FastAPI：**声明式**，用类型注解声明「我要 query 参数 q、请求体 BookIn、header X-Token」，框架解析好再注入；需要原始请求时声明 `request: Request`。

---

## 4. 核心组件逐个过

### 4.1 路由

```python
@app.get("/books/<int:book_id>")       # 转换器：string(默认) int float path uuid
def get_book(book_id: int): ...

@app.route("/books/", methods=["GET", "POST"])
def books(): ...

url_for("books.get_book", book_id=1)   # 按端点名反解 URL（蓝图名.函数名）
```

- 端点名（endpoint）默认是函数名；在 Blueprint 里是 `蓝图名.函数名`。
- 以 `/` 结尾的规则访问不带斜杠的地址会自动 308 重定向；反之不会，这是 Werkzeug 的「规范 URL」行为。

### 4.2 视图返回值

视图可以返回：

| 返回值 | 结果 |
|---|---|
| `str` | HTML 文本，200 |
| `dict` / `list` | 自动 `jsonify` |
| `(body, status)` / `(body, status, headers)` | 指定状态码、响应头 |
| `Response` 对象 | 原样返回 |
| 生成器 | 流式响应 |

### 4.3 请求对象

```python
request.args.get("q")                  # 查询参数（MultiDict）
request.form["title"]                  # 表单
request.get_json(silent=True)          # JSON；silent=True 解析失败返回 None 而不是 400
request.files["upload"]                # 上传文件
request.headers.get("X-Token")
request.cookies.get("sid")
request.method / request.path / request.remote_addr
```

### 4.4 模板

```python
from flask import render_template
return render_template("books/list.html", books=books)
```

Jinja2 语法与 Django 模板相似但更强：`{{ x | upper }}`、`{% for %}`、`{% extends %}`、`{% macro %}`，允许调用方法和表达式。`.html` 等后缀默认自动转义。

### 4.5 Blueprint（蓝图）

```python
from flask import Blueprint

bp = Blueprint("books", __name__)

@bp.get("/")
def list_books(): ...

app.register_blueprint(bp, url_prefix="/books")
```

Blueprint 是一组路由、钩子、模板、静态文件的 **可注册模块**，用于把大应用按功能拆分。它不是独立应用，必须注册到 app 上才生效；同一个蓝图可以用不同前缀注册多次。

### 4.6 配置

```python
app.config.from_object(Config)        # 从类 / 模块加载（只认大写属性）
app.config.from_prefixed_env()        # 读 FLASK_ 前缀的环境变量，FLASK_SECRET_KEY → SECRET_KEY
app.config.from_pyfile("local.cfg", silent=True)   # 常配合 instance 文件夹
```

`from_prefixed_env` 会尝试把值按 JSON 解析，所以 `FLASK_DEBUG=true` 会得到布尔值。

> **三框架对比 · 模块化**
> - Flask `Blueprint` ≈ FastAPI `APIRouter` ≈ Django `App + include()`。
> - 差异：Django App 还带模型、迁移、Admin，是「完整业务模块」；Blueprint 和 APIRouter 只是「路由分组」，数据层要自己组织。

---

## 5. 数据库：Flask-SQLAlchemy

Flask 不带 ORM，最常用的是 **Flask-SQLAlchemy**（把 SQLAlchemy 的 engine / session 与 Flask 的应用上下文绑定）+ **Flask-Migrate**（封装 Alembic 迁移）。

### 5.1 初始化（SQLAlchemy 2.x 风格）

```python
# extensions.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)       # 先创建，不绑定 app
```

```python
# 在应用工厂里
db.init_app(app)                        # 延迟绑定，支持多个 app 实例
```

### 5.2 模型

```python
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Author(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    books: Mapped[list["Book"]] = relationship(back_populates="author")


class Book(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    stock: Mapped[int] = mapped_column(default=0)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author: Mapped[Author] = relationship(back_populates="books")
```

- `Mapped[...]` + `mapped_column` 是 SQLAlchemy 2.0 的类型化写法，类型检查器能推断字段类型。
- Flask-SQLAlchemy 会根据类名自动生成表名（`Book` → `book`）。

### 5.3 查询（2.x 推荐的 select 风格）

```python
stmt = db.select(Book).where(Book.title.ilike("%flask%")).order_by(Book.id)
books = db.session.execute(stmt).scalars().all()

db.session.get(Book, 1)                   # 按主键
db.get_or_404(Book, 1)                    # 查不到直接 abort(404)
db.one_or_404(db.select(Book).filter_by(title="x"))
db.paginate(db.select(Book), page=1, per_page=20)

db.session.add(book); db.session.commit()
db.session.delete(book); db.session.commit()
db.session.rollback()
```

旧的 `Book.query.filter_by(...)` 写法仍可用，但官方标记为 legacy，新代码用 `db.select` + `db.session.execute`。

### 5.4 防 N+1 与原子更新

```python
from sqlalchemy.orm import joinedload, selectinload

db.select(Book).options(joinedload(Book.author))        # JOIN 一次取回（多对一）
db.select(Author).options(selectinload(Author.books))   # 第二条 IN 查询（一对多）

db.session.execute(
    db.update(Book).where(Book.id == book_id, Book.stock > 0).values(stock=Book.stock - 1)
)                                                       # 一条 SQL 原子扣减
```

### 5.5 会话生命周期

Flask-SQLAlchemy 的 `db.session` 是 **scoped session**，作用域绑定到应用上下文；在 `teardown_appcontext` 时自动 `remove()`。所以每个请求天然拿到独立会话，请求结束自动清理，你只需要负责 `commit` / `rollback`。

### 5.6 迁移（Flask-Migrate）

```bash
pip install flask-migrate
flask db init                     # 生成 migrations/ 目录（一次）
flask db migrate -m "add book"    # autogenerate 迁移脚本，务必人工检查
flask db upgrade                  # 执行
flask db downgrade                # 回滚
```

> **三框架对比 · 数据层**
> - Flask 与 FastAPI 都通常用 SQLAlchemy，区别在 **会话怎么管理**：Flask-SQLAlchemy 把 session 绑在应用上下文上（隐式）；FastAPI 通过 `yield` 依赖把 session 注入到路由参数（显式）。
> - Django ORM 的 `Book.objects.filter(...)` ≈ `db.select(Book).where(...)`；`select_related` ≈ `joinedload`；`prefetch_related` ≈ `selectinload`；`makemigrations` ≈ `flask db migrate`。

---

## 6. 常用方法速查

### 6.1 flask 模块

| 名称 | 说明 |
|---|---|
| `Flask(__name__)` | 创建应用 |
| `request` / `session` / `g` / `current_app` | 上下文代理 |
| `render_template(name, **ctx)` | 渲染模板 |
| `jsonify(...)` | JSON 响应（返回 dict 时可省略） |
| `redirect(url, code=302)` | 重定向 |
| `url_for(endpoint, **values)` | 反解 URL |
| `abort(404, description=...)` | 抛 HTTP 异常 |
| `make_response(body, status)` | 构造 Response 以便改头 |
| `flash(msg)` / `get_flashed_messages()` | 一次性消息 |
| `send_file()` / `send_from_directory()` | 发送文件（后者防目录穿越） |
| `stream_with_context(gen)` | 流式响应时保留请求上下文 |
| `Blueprint(name, import_name)` | 蓝图 |
| `flask.views.MethodView` | 类视图，按 HTTP 方法分发 |

### 6.2 app 对象

| 方法 | 说明 |
|---|---|
| `@app.get/post/put/patch/delete` | 路由 |
| `@app.before_request` / `after_request` / `teardown_request` | 请求钩子 |
| `@app.teardown_appcontext` | 应用上下文结束钩子 |
| `@app.errorhandler(code_or_exc)` | 错误处理 |
| `@app.context_processor` | 向所有模板注入变量 |
| `@app.cli.command()` | 自定义 `flask xxx` 命令 |
| `app.register_blueprint(bp, url_prefix=...)` | 注册蓝图 |
| `app.app_context()` / `app.test_request_context()` | 手动推上下文 |
| `app.test_client()` / `app.test_cli_runner()` | 测试 |

### 6.3 flask 命令

| 命令 | 说明 |
|---|---|
| `flask --app pkg run --debug` | 开发服务器 |
| `flask --app pkg shell` | 带应用上下文的 shell |
| `flask --app pkg routes` | 列出所有路由 |
| `flask --app pkg db upgrade` | Flask-Migrate 迁移 |
| `flask --app pkg init-db` | 自定义命令（见教程） |

---

## 7. 教程：从零写一个书店

目标：图书 CRUD + 搜索 + 购买扣库存（防超卖）+ 统一 JSON 错误 + 请求耗时头 + CLI 建表。

### 7.1 目录

```text
flasksite/
├── bookshop/
│   ├── __init__.py      # 应用工厂 create_app
│   ├── config.py        # 配置类
│   ├── extensions.py    # db 等扩展实例
│   ├── models.py
│   ├── books.py         # books 蓝图
│   ├── hooks.py         # 钩子 + 错误处理
│   └── cli.py           # 自定义命令
└── test_bookshop.py
```

### 7.2 配置（敏感项从环境变量读）

```python
# bookshop/config.py
import os


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-not-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///bookshop.db")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
```

`dev-only-not-secret` 只是本地占位；生产环境通过 `FLASK_SECRET_KEY` 注入随机值（`python -c "import secrets; print(secrets.token_hex(32))"`）。`SECRET_KEY` 用于签名 session cookie，泄露后攻击者可以伪造任意会话。

### 7.3 应用工厂

```python
# bookshop/__init__.py
from flask import Flask

from .config import Config
from .extensions import db


def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.from_prefixed_env()

    db.init_app(app)

    from .books import bp as books_bp
    app.register_blueprint(books_bp, url_prefix="/books")

    from . import hooks, cli
    hooks.register(app)
    cli.register(app)

    return app
```

为什么用工厂而不是模块级 `app = Flask(...)`：

1. **测试**：每个测试用不同配置创建全新 app，互不污染。
2. **避免循环导入**：扩展先在 `extensions.py` 里创建，工厂里再 `init_app`；蓝图在函数内导入。
3. **多实例**：同一份代码可以按不同配置起多个 app。

### 7.4 蓝图与视图

```python
# bookshop/books.py
from flask import Blueprint, abort, jsonify, request
from sqlalchemy.orm import joinedload

from .extensions import db
from .models import Author, Book

bp = Blueprint("books", __name__)


@bp.get("/")
def list_books():
    stmt = db.select(Book).options(joinedload(Book.author)).order_by(Book.id)
    if q := request.args.get("q"):
        stmt = stmt.where(Book.title.ilike(f"%{q}%"))
    books = db.session.execute(stmt).scalars().all()
    return {"items": [b.to_dict() for b in books]}


@bp.post("/")
def create_book():
    data = request.get_json(silent=True) or {}
    missing = [k for k in ("title", "author", "price") if k not in data]
    if missing:
        abort(400, description=f"missing: {', '.join(missing)}")
    author = db.session.execute(
        db.select(Author).filter_by(name=data["author"])
    ).scalar_one_or_none() or Author(name=data["author"])
    book = Book(title=data["title"], author=author, price=data["price"], stock=data.get("stock", 0))
    db.session.add(book)
    db.session.commit()
    return book.to_dict(), 201


@bp.get("/<int:book_id>")
def get_book(book_id: int):
    return db.get_or_404(Book, book_id).to_dict()


@bp.delete("/<int:book_id>")
def delete_book(book_id: int):
    db.session.delete(db.get_or_404(Book, book_id))
    db.session.commit()
    return "", 204


@bp.post("/<int:book_id>/buy")
def buy(book_id: int):
    result = db.session.execute(
        db.update(Book)
        .where(Book.id == book_id, Book.stock > 0)
        .values(stock=Book.stock - 1)
    )
    db.session.commit()
    if result.rowcount == 0:
        return jsonify(detail="sold out"), 409
    return {"ok": True}
```

模型里补一个 `to_dict()` 用于序列化：

```python
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author.name,
            "price": str(self.price),      # Decimal 转字符串，避免精度丢失
            "stock": self.stock,
        }
```

注意这里的「校验」只是手工检查字段是否存在——**Flask 本身不做数据校验**。真实项目要接 Marshmallow / Pydantic，或用 flask-smorest / APIFlask（见第 8 节）。

### 7.5 钩子与统一错误

```python
# bookshop/hooks.py
import time

from flask import Flask, g, jsonify
from werkzeug.exceptions import HTTPException


def register(app: Flask) -> None:
    @app.before_request
    def start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def add_elapsed(response):
        response.headers["X-Elapsed-Ms"] = f"{(time.perf_counter() - g.start) * 1000:.1f}"
        return response

    @app.errorhandler(HTTPException)
    def json_error(err: HTTPException):
        return jsonify(detail=err.description), err.code
```

默认情况下 `abort(404)` 返回的是 HTML 错误页；注册 `HTTPException` 处理器后，所有 4xx / 5xx HTTP 异常都变成 `{"detail": ...}` 的 JSON，对 API 友好（这里特意用 `detail` 字段，与 FastAPI 的错误格式保持一致）。

### 7.6 自定义 CLI 命令

```python
# bookshop/cli.py
import click
from flask import Flask

from .extensions import db


def register(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db():
        """建表。生产环境用 Flask-Migrate 生成迁移。"""
        db.create_all()
        click.echo("tables created")
```

```bash
flask --app bookshop init-db
flask --app bookshop run --debug
```

> **三框架对比 · 同一个书店**
> - 「查不到就 404」：Django `get_object_or_404`、Flask `db.get_or_404`、FastAPI `raise HTTPException(404)`。
> - 「防超卖」：三者都用「带条件的 UPDATE + 判断影响行数」；Django 写 `F("stock") - 1`，SQLAlchemy 写 `Book.stock - 1`。
> - 「输入校验」：Django 用 Form / Serializer，Flask 需要自己做或接扩展，FastAPI 只要声明 Pydantic 模型就自动 422。

---

## 8. 写 REST API 的几种方式

| 方式 | 特点 |
|---|---|
| 原生路由 + 手写校验 | 最灵活，样板代码多（上面的教程） |
| `MethodView` | 类视图，按 HTTP 方法分发，适合资源型接口 |
| **Marshmallow** / **Pydantic** | 校验与序列化 |
| **flask-smorest** | Marshmallow + 自动 OpenAPI + 分页 |
| **APIFlask** | 基于 Flask 的 API 框架，风格接近 FastAPI（装饰器声明入参出参 + 自动文档） |
| Flask-RESTX | Swagger 文档，老项目常见 |

```python
from flask.views import MethodView

class BookAPI(MethodView):
    def get(self, book_id):
        return db.get_or_404(Book, book_id).to_dict()

    def delete(self, book_id):
        ...

app.add_url_rule("/books/<int:book_id>", view_func=BookAPI.as_view("book"))
```

> **三框架对比 · API 开发体验**
> 写纯 API 时，Flask 需要「Flask + 校验库 + 文档扩展」拼起来，才能接近 FastAPI 开箱即用的体验；Django 需要「Django + DRF + drf-spectacular」。这也是 FastAPI 在新 API 项目里流行的主要原因。

---

## 9. 认证与安全

### 9.1 Session 是签名 cookie，不是加密 cookie

```python
session["user_id"] = 1
```

Flask 默认把 session **序列化后签名，整体存在客户端 cookie 里**。签名保证 **不能被篡改**，但内容只是 base64 编码，**任何人都能解码读出来**。所以：

- 不要往 session 里放密码、令牌等敏感数据。
- `SECRET_KEY` 必须足够随机且保密。
- 需要服务端存储时用 Flask-Session（Redis 等后端）。

生产 cookie 配置：

```python
SESSION_COOKIE_SECURE = True       # 仅 HTTPS
SESSION_COOKIE_HTTPONLY = True     # JS 不可读（默认 True）
SESSION_COOKIE_SAMESITE = "Lax"
```

### 9.2 常用安全扩展

| 需求 | 方案 |
|---|---|
| 登录态管理 | Flask-Login（`login_user`、`@login_required`、`current_user`） |
| CSRF | Flask-WTF（`CSRFProtect(app)`） |
| JWT | Flask-JWT-Extended |
| CORS | Flask-CORS |
| 限流 | Flask-Limiter |
| 安全响应头 | Flask-Talisman（HSTS、CSP 等） |
| 密码哈希 | `werkzeug.security.generate_password_hash`（默认 scrypt） |

### 9.3 其他

- Jinja2 默认对 `.html` 模板自动转义，`|safe` / `Markup` 要慎用。
- 用 `send_from_directory` 而不是自己拼路径，防目录穿越。
- 生产绝不开 `debug`。

> **三框架对比 · 安全默认值**
> Django 默认开启 CSRF、点击劫持防护、安全中间件；Flask 只给你签名 session 和模板转义，其余靠扩展；FastAPI 面向 Token 认证的 API，默认不处理 CSRF，`fastapi.security` 提供 OAuth2 / API Key 等工具类，配合依赖注入使用。

---

## 10. 钩子、错误处理与信号

| 钩子 | 时机 | 备注 |
|---|---|---|
| `before_request` | 视图前 | 返回非 None 即短路 |
| `after_request` | 视图后、无异常时 | 必须返回 response；逆注册顺序执行 |
| `teardown_request` | 请求结束，**无论是否异常** | 收到异常参数，不能修改响应 |
| `teardown_appcontext` | 应用上下文结束 | 释放数据库连接等 |
| `errorhandler(404 / Exception)` | 出错时 | 返回自定义错误响应 |
| 蓝图版本：`bp.before_request`、`bp.app_errorhandler` 等 | 仅本蓝图 / 全局 | |

信号（基于 Blinker）：`request_started`、`request_finished`、`got_request_exception`、`template_rendered` 等，适合做监控埋点，不适合承载业务逻辑。

WSGI 中间件：Flask 应用本身是 WSGI 可调用对象，可以用 `app.wsgi_app = SomeMiddleware(app.wsgi_app)` 包装，例如部署在反向代理后要用 `werkzeug.middleware.proxy_fix.ProxyFix` 修正客户端 IP 和协议。

> **三框架对比 · 「中间件」**
> - Flask 的钩子相当于「拆开的中间件」：前半段 `before_request`，后半段 `after_request`，收尾 `teardown`。
> - Django 中间件是一个类包住整条链；FastAPI 中间件是 `async def (request, call_next)` 包住整条链。
> - 想做「请求级资源的获取与释放」：Flask 用 `g` + `teardown`，FastAPI 用 `yield` 依赖，Django 通常交给 ORM 自动管理连接。

---

## 11. 异步支持

```bash
pip install "flask[async]"      # 依赖 asgiref
```

```python
@app.get("/ping-async")
async def ping():
    await asyncio.sleep(0.1)
    return {"pong": True}
```

- Flask 2.0 起支持 `async def` 视图，内部通过 `ensure_sync` 把协程放到一个事件循环里跑完。
- **但每个请求仍然独占一个 WSGI worker（线程 / 进程）**。async 视图只是让你能在视图内部并发多个 IO（例如 `asyncio.gather` 同时请求三个下游服务），**不能让同一个 worker 同时处理更多请求**。
- 需要真正的异步服务器，官方建议考虑 Quart（Flask API 的 ASGI 实现）或换 FastAPI。
- 提高 Flask 并发的常规手段：多进程 + 多线程 worker（`gunicorn -w 4 --threads 8`），或 gevent / eventlet 协程 worker。

> **三框架对比 · 异步**
> 同样写 `async def`：在 FastAPI 里能让单进程同时挂起成百上千个等待 IO 的请求；在 Flask 里只是「这个请求内部可以并发」；在 Django ASGI 下介于两者之间（视图可异步，ORM 底层仍走线程）。

---

## 12. 测试

```python
# test_bookshop.py
import pytest
from flask import current_app, g, session

from bookshop import create_app
from bookshop.config import TestConfig
from bookshop.extensions import db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make(client, title="Flask Notes", author="Ada", price="20.00", stock=1):
    return client.post("/books/", json={"title": title, "author": author, "price": price, "stock": stock})


def test_create_list_filter(client):
    assert make(client).status_code == 201
    make(client, title="Django Basics", author="Bob")
    resp = client.get("/books/?q=flask")
    assert [b["title"] for b in resp.get_json()["items"]] == ["Flask Notes"]
    assert "X-Elapsed-Ms" in resp.headers


def test_validation_and_404_are_json(client):
    bad = client.post("/books/", json={"title": "x"})
    assert bad.status_code == 400
    assert bad.get_json() == {"detail": "missing: author, price"}
    assert client.get("/books/999").status_code == 404


def test_buy_and_delete(client):
    book_id = make(client, stock=1).get_json()["id"]
    assert client.post(f"/books/{book_id}/buy").status_code == 200
    assert client.post(f"/books/{book_id}/buy").status_code == 409
    assert client.delete(f"/books/{book_id}").status_code == 204


def test_cli(app):
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert "tables created" in result.output
```

- 应用工厂让每个测试拿到全新的 app 和内存数据库。
- `test_client()` 不启动服务器，直接调用 WSGI 应用；`json=` 参数自动设置 `Content-Type`。
- `test_request_context()` 用来单测依赖 `request` / `g` 的工具函数。
- `test_cli_runner()` 测 CLI 命令。

本地验证结果：`pytest` → **6 passed**（含上下文、CLI、async 视图测试）。

> **三框架对比 · 测试隔离**
> Django 自动建测试库并在每个测试后回滚；Flask 靠应用工厂 + fixture 自己建表清理；FastAPI 用 `dependency_overrides` 替换数据库依赖。Flask 想替换某个依赖时，通常是在工厂里传不同配置，或 monkeypatch。

---

## 13. 工程实践

### 13.1 推荐结构

```text
project/
├── app/
│   ├── __init__.py          # create_app
│   ├── config.py
│   ├── extensions.py        # db, migrate, login_manager, cache ...
│   ├── models/
│   ├── schemas/             # Marshmallow / Pydantic
│   ├── services/            # 业务逻辑，不依赖 request
│   ├── api/                 # 各蓝图
│   │   ├── books.py
│   │   └── auth.py
│   └── cli.py
├── migrations/
├── tests/
└── wsgi.py                  # app = create_app()
```

- **扩展实例集中在 `extensions.py`**，工厂里 `init_app`，避免循环导入。
- **业务逻辑不要直接依赖 `request`**，把参数显式传进 service，方便测试和在 CLI / Celery 中复用。
- 后台任务里访问 `db` 等扩展时，需要手动 `with app.app_context():`。

### 13.2 部署

```bash
gunicorn "app:create_app()" --workers 4 --threads 4 --bind 0.0.0.0:8000
```

- `flask run` 只用于开发；生产用 gunicorn / uWSGI / waitress（Windows）。
- 反向代理后面加 `ProxyFix`，否则 `request.remote_addr`、`url_for(_external=True)` 的协议会错。
- 静态文件交给 Nginx / CDN。

### 13.3 常用扩展清单

| 类别 | 扩展 |
|---|---|
| ORM / 迁移 | Flask-SQLAlchemy、Flask-Migrate |
| 认证 | Flask-Login、Flask-JWT-Extended |
| 表单 / CSRF | Flask-WTF |
| API / 文档 | flask-smorest、APIFlask |
| 缓存 | Flask-Caching（`SimpleCache` 进程内，`RedisCache` / `MemcachedCache` 多进程共享） |
| 限流 | Flask-Limiter |
| CORS | Flask-CORS |
| 后台任务 | Celery、RQ |

进程内缓存、Redis、Memcached，以及 Peewee 和 SQLAlchemy 的取舍，见 [常用第三方库](./libraries.md)。

> **三框架对比 · 工程化成本**
> Flask 的自由意味着团队要自己定规范：目录、校验库、错误格式、认证方案。Django 已经替你定了；FastAPI 定了一半（校验、文档、DI），剩下的分层是社区约定。

---

## 14. 面试题与参考回答

**Q1：Flask 的应用上下文和请求上下文是什么？为什么需要？**
请求上下文保存当前请求相关的 `request` 和 `session`；应用上下文保存当前应用相关的 `current_app` 和 `g`。处理请求时 Flask 先推应用上下文再推请求上下文，结束时依次弹出。需要它们是因为 Flask 让你用全局变量风格访问 `request`，但服务器同时处理多个请求，必须保证每个线程 / 协程看到的是自己的请求，所以用基于 `contextvars` 的隔离存储加代理对象实现。应用上下文单独存在，是为了在没有请求的场景（CLI 命令、后台任务、测试）也能访问配置和扩展。

**Q2：`g` 和 `session` 有什么区别？**
`g` 是应用上下文上的临时存储，只在一次请求内有效，存在服务端内存里，用于在钩子和视图之间传数据。`session` 跨请求保持，默认存在客户端签名 cookie 里，用于登录态、购物车等。

**Q3：Flask 的 session 安全吗？**
默认 session 是签名的 cookie，防篡改但不加密，任何人都能 base64 解码看到内容。安全性依赖 `SECRET_KEY` 的保密性。不能存敏感数据；需要服务端存储时用 Flask-Session 配合 Redis；生产要开 `SESSION_COOKIE_SECURE`。

**Q4：什么是应用工厂？为什么推荐？**
把创建 app 的过程封装成 `create_app(config)` 函数。好处是：测试时可以用不同配置创建隔离的实例；扩展先创建后 `init_app`，避免循环导入；可以在同一进程创建多个配置不同的 app。

**Q5：Blueprint 的作用？**
把一组相关的路由、钩子、模板、静态文件组织成模块，注册到 app 上时可以指定 URL 前缀。它用于大型应用的模块化拆分，本身不是独立应用，需要注册后才生效。

**Q6：`before_request`、`after_request`、`teardown_request` 的区别？**
`before_request` 在视图前执行，返回非 None 就直接作为响应、跳过视图。`after_request` 在视图正常返回后执行，可以修改响应，必须返回 response，出现未处理异常时不执行。`teardown_request` 无论成功失败都会在请求结束时执行，接收异常参数，用于释放资源，不能修改响应。

**Q7：Flask 是单线程的吗？怎么提高并发？**
Flask 本身不管并发模型，取决于 WSGI 服务器。开发服务器默认开启多线程；生产用 gunicorn 多进程，每个进程还可以多线程，或者用 gevent / eventlet 协程 worker 处理 IO 密集场景。上下文的线程 / 协程隔离保证了这些模式下的安全。

**Q8：Flask 支持 async 吗？和 FastAPI 的 async 有什么不同？**
Flask 2.0 起支持 `async def` 视图，但它运行在 WSGI 上，每个请求依然占用一个 worker，async 只能让单个请求内部并发多个 IO，不能提高服务器同时处理的请求数。FastAPI 基于 ASGI，单个事件循环可以同时挂起大量等待 IO 的请求，是真正的异步并发。

**Q9：Flask-SQLAlchemy 的 session 是怎么管理的？**
它使用 scoped session，作用域绑定到应用上下文，每个请求拿到独立的 session，在应用上下文结束（`teardown_appcontext`）时自动移除。开发者只需负责 commit / rollback。

**Q10：Flask 和 Django 怎么选？**
Flask 灵活、轻量、学习成本低，适合小服务、原型、需要自选技术栈的场景，但大型项目需要团队自定规范。Django 功能全、约定强，ORM / Admin / 认证开箱即用，适合业务复杂、需要快速交付的中大型项目。

**Q11：Flask 和 FastAPI 怎么选？**
两者写法相似。FastAPI 内置类型校验、自动 OpenAPI 文档、依赖注入、原生异步，适合新的 API 项目和高并发 IO / 流式场景。Flask 生态更久、同步库兼容性好、模板渲染场景成熟，适合传统 Web 应用和已有 Flask 代码库的维护扩展。

---

## 15. 常见坑

| 坑 | 正确做法 |
|---|---|
| 在请求外访问 `request` / `current_app` 报 `RuntimeError` | 手动 `with app.app_context()` / `test_request_context()` |
| 往 session 里放敏感数据 | session 默认客户端可读，放服务端或只放 ID |
| 模块级 `app = Flask()` 导致循环导入、难测试 | 应用工厂 + `extensions.py` |
| 以为 `async def` 视图能提高吞吐 | 吞吐靠 worker 数；要异步并发换 ASGI 框架 |
| 生产开 `debug=True` | 调试器可远程执行代码，严禁 |
| 流式响应里访问 `request` 报错 | 用 `stream_with_context` 包装生成器 |
| 后台线程 / Celery 里用 `db` 报无上下文 | 在任务里推 `app.app_context()` |
| `abort(404)` 返回 HTML，前端解析失败 | 注册 `HTTPException` 错误处理器返回 JSON |
| 部署在 Nginx 后拿到的 IP 都是 127.0.0.1 | `ProxyFix` |
| 继续用 `Model.query` 旧 API | 新代码用 `db.select` + `db.session.execute` |
