# Django 手记：核心用法 · 常用方法 · 教程 · 工程实践 · 面试

> 系列文档：**Django** · [Flask](./flask.md) · [FastAPI](./fastapi.md) · [常用第三方库](./libraries.md)
>
> 三份文档用同一个「书店 Bookshop」例子（作者 / 图书 / 库存 / 购买），方便横向对照。文中所有代码都在本地真实跑过测试。
>
> 验证环境：Python 3.12 · Django 6.1.2 · Django REST framework 3.18.3（2026-10）。
> 生产项目若追求长期支持，可选 **Django 5.2 LTS**（支持到 2028-04）；本文涉及 6.x 新特性的地方会单独标注。

文中带 **「三框架对比」** 的引用块，专门说明此处与 Flask / FastAPI 的相同与不同。

---

## 目录

1. [定位：Django 是什么、适合什么](#1-定位django-是什么适合什么)
2. [安装与最小项目](#2-安装与最小项目)
3. [请求生命周期](#3-请求生命周期)
4. [核心组件逐个过](#4-核心组件逐个过)
5. [ORM 深入](#5-orm-深入)
6. [常用方法速查](#6-常用方法速查)
7. [教程：从零写一个书店](#7-教程从零写一个书店)
8. [Django REST framework（DRF）](#8-django-rest-frameworkdrf)
9. [认证、权限与安全](#9-认证权限与安全)
10. [中间件与信号](#10-中间件与信号)
11. [异步支持](#11-异步支持)
12. [后台任务](#12-后台任务)
13. [测试](#13-测试)
14. [工程实践](#14-工程实践)
15. [面试题与参考回答](#15-面试题与参考回答)
16. [常见坑](#16-常见坑)

---

## 1. 定位：Django 是什么、适合什么

Django 是 **「自带电池」（batteries included）** 的全栈 Web 框架：ORM、迁移、Admin 后台、认证、表单、模板、缓存、国际化、安全防护都内置，并且彼此深度集成。

| 维度 | Django | Flask | FastAPI |
|---|---|---|---|
| 哲学 | 大而全，约定优于配置 | 微内核，按需组装 | 类型驱动，API 优先 |
| 协议 | WSGI 为主，支持 ASGI | WSGI | ASGI |
| ORM | 内置 Django ORM | 无（常配 SQLAlchemy） | 无（常配 SQLAlchemy / SQLModel） |
| 数据校验 | Form / DRF Serializer | 无（常配 Marshmallow / Pydantic） | Pydantic（内置） |
| 后台管理 | 内置 Admin | 无（Flask-Admin） | 无 |
| API 文档 | 需 drf-spectacular 等 | 需扩展 | 自动生成 OpenAPI |
| 典型场景 | 内容站、后台系统、电商、SaaS | 小服务、原型、高度定制 | 高并发 API、AI / LLM 服务 |

**什么时候选 Django**：业务模型多、需要后台管理、需要用户体系、团队希望统一规范、交付速度优先。
**什么时候不选**：只是几个 JSON 接口的轻服务，或是重度 IO 并发 / 流式输出（FastAPI 更合适）。

> **三框架对比 · 设计哲学**
> - **相同**：三者都是「路由 → 视图函数 → 返回响应」的基本模型，都支持中间件、都能接 SQLAlchemy 之外的数据库层。
> - **不同**：Django 给你「一整套房子」；Flask 给你「地基和工具箱」；FastAPI 给你「一套以类型注解为图纸的 API 生产线」。

---

## 2. 安装与最小项目

```bash
python -m venv .venv && source .venv/bin/activate
pip install "django>=6.1,<6.2" djangorestframework

django-admin startproject config .     # 项目（配置容器）
python manage.py startapp books        # 应用（业务模块）
python manage.py migrate               # 建内置表（auth / session / admin ...）
python manage.py createsuperuser       # 后台管理员
python manage.py runserver             # 开发服务器 http://127.0.0.1:8000
```

生成的结构：

```text
.
├── manage.py              # 命令行入口（等价于 django-admin + 指定 settings）
├── config/                # 项目 = 配置
│   ├── settings.py        # 全局配置
│   ├── urls.py            # 根路由
│   ├── wsgi.py            # WSGI 入口（gunicorn 用）
│   └── asgi.py            # ASGI 入口（uvicorn / daphne 用）
└── books/                 # 应用 = 业务模块，可复用
    ├── models.py  views.py  admin.py  apps.py  tests.py
    └── migrations/
```

**Project vs App**：Project 是一个站点的配置集合；App 是一个可插拔的功能模块。一个 Project 包含多个 App，一个 App 也可以被多个 Project 复用（比如 `django.contrib.auth` 就是一个 App）。新建 App 后必须加进 `INSTALLED_APPS`，否则模型、迁移、模板、Admin 都不会被发现。

**MTV 模式**：Model（数据）– Template（展示）– View（逻辑）。它就是 MVC 换了个名字：Django 的 View 相当于 MVC 的 Controller，Template 相当于 MVC 的 View，而「框架本身的 URL 分发」扮演了一部分 Controller 角色。

> **三框架对比 · 起步成本**
> - Django：`startproject` 一条命令生成完整骨架，强约定目录。
> - Flask：一个文件 5 行即可跑，目录结构完全自定。
> - FastAPI：同样一个文件即可跑，`fastapi dev main.py` 启动。

---

## 3. 请求生命周期

```text
客户端
  │  HTTP
  ▼
Web 服务器（Nginx）──► 应用服务器（gunicorn: WSGI / uvicorn: ASGI）
  │
  ▼
WSGIHandler / ASGIHandler   ← 构造 HttpRequest
  │
  ▼
中间件（请求方向，按 MIDDLEWARE 列表从上到下）
  │  SecurityMiddleware → SessionMiddleware → CommonMiddleware
  │  → CsrfViewMiddleware → AuthenticationMiddleware → ...
  ▼
URL 解析（ROOT_URLCONF → urlpatterns 逐条匹配）
  │
  ▼
视图 view(request, **kwargs)  ── ORM 查询 ── 模板渲染
  │  返回 HttpResponse
  ▼
中间件（响应方向，从下到上）
  │
  ▼
客户端
```

要点：

- 中间件是 **洋葱模型**：列表靠前的中间件，请求时最先执行，响应时最后执行。
- `request.user` 是 `AuthenticationMiddleware` 挂上去的，所以它必须排在 `SessionMiddleware` 之后。
- URL 按顺序匹配，**第一个匹配就停**。
- 视图抛出 `Http404` 会被框架转成 404 页面；未捕获异常在 `DEBUG=False` 时变成 500。

> **三框架对比 · 生命周期**
> - **相同**：三者都是「服务器 → 中间件 → 路由 → 视图 → 中间件 → 响应」的洋葱结构。
> - **不同**：Django 中间件是类，配置在 `settings.MIDDLEWARE` 列表里；Flask 用 `before_request` / `after_request` 钩子 + WSGI 中间件；FastAPI 用 `@app.middleware("http")` 或 Starlette 的 ASGI 中间件类，另外有一套独立的 **依赖注入** 在路由层生效。

---

## 4. 核心组件逐个过

### 4.1 URL 路由

```python
# books/urls.py
from django.urls import include, path

app_name = "books"                     # 命名空间，reverse("books:detail", args=[1])
urlpatterns = [
    path("books/", views.book_list, name="list"),
    path("books/<int:pk>/", views.BookDetailView.as_view(), name="detail"),
]

# config/urls.py
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("books.urls")),   # 挂载子路由
]
```

- 路径转换器：`str`（默认，不含 `/`）、`int`、`slug`、`uuid`、`path`（含 `/`）。复杂规则用 `re_path`。
- **永远用 `name` + `reverse()` / 模板里的 `{% url %}` 生成链接**，不要手写路径字符串。

### 4.2 视图：FBV、CBV、通用视图

```python
# 函数视图 FBV：直观，适合简单逻辑
@require_http_methods(["GET", "POST"])
def book_list(request): ...

# 类视图 CBV：按 HTTP 方法分发到同名方法
class BookDetailView(View):
    def get(self, request, pk): ...
    def delete(self, request, pk): ...

# 通用视图 Generic View：常见 CRUD 一行搞定（服务端渲染场景）
from django.views.generic import ListView, DetailView
class BookListView(ListView):
    model = Book
    paginate_by = 20
    template_name = "books/list.html"
```

- `View.as_view()` 返回一个函数，每个请求都会 **新建一个视图实例**，所以在 `self` 上存请求级状态是安全的。
- CBV 通过 Mixin 复用（`LoginRequiredMixin`、`PermissionRequiredMixin`），注意 Mixin 要放在基类左边。

### 4.3 模板

```django
{% extends "base.html" %}
{% block content %}
  <h1>{{ book.title|upper }}</h1>
  {% for b in books %}
    <a href="{% url 'books:detail' b.pk %}">{{ b.title }}</a>
  {% empty %}
    <p>暂无图书</p>
  {% endfor %}
  <form method="post">{% csrf_token %} ... </form>
{% endblock %}
```

- 默认 **自动 HTML 转义**，防 XSS；确需输出 HTML 时用 `|safe` 或 `mark_safe`，并确保内容可信。
- 模板语言有意「弱」：不允许任意 Python 表达式，逻辑应放在视图里。
- Django 6.0 起内置 **模板片段（template partials）**：`{% partialdef %}` / `{% partial %}`，适合 htmx 局部刷新。

### 4.4 表单

```python
from django import forms

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ["title", "author", "price", "stock"]

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price <= 0:
            raise forms.ValidationError("价格必须大于 0")
        return price

def create(request):
    form = BookForm(request.POST or None)
    if form.is_valid():                # 触发字段校验 + clean_<field> + clean()
        form.save()
        return redirect("books:list")
    return render(request, "books/form.html", {"form": form})
```

Form 负责三件事：**渲染 HTML 控件、校验输入、把干净数据转成 Python 对象**。做纯 JSON API 时，这个角色由 DRF 的 Serializer 承担。

### 4.5 Settings

| 配置 | 作用 | 生产注意 |
|---|---|---|
| `SECRET_KEY` | 签名 session、CSRF、密码重置令牌 | **必须**从环境变量读，泄露即可伪造会话 |
| `DEBUG` | 调试页面、详细报错 | 生产必须 `False` |
| `ALLOWED_HOSTS` | 防 Host 头攻击 | 生产必须显式列出域名 |
| `DATABASES` | 数据库连接 | 配 `CONN_MAX_AGE` 复用连接 |
| `INSTALLED_APPS` | 启用的应用 | 顺序影响模板 / 静态文件查找优先级 |
| `MIDDLEWARE` | 中间件链 | 顺序有语义 |
| `STATIC_ROOT` / `STATIC_URL` | 静态文件 | 部署前 `collectstatic` |
| `CACHES` | 缓存后端 | 生产用 Redis |

> **三框架对比 · 配置**
> - Django：一个全局 `settings.py` 模块，通过 `DJANGO_SETTINGS_MODULE` 指定，`from django.conf import settings` 读取。
> - Flask：`app.config` 字典，`from_object` / `from_prefixed_env` 加载，按 app 实例隔离。
> - FastAPI：框架不管配置，惯例用 `pydantic-settings` 的 `BaseSettings`，带类型校验，再通过依赖注入拿到。

---

## 5. ORM 深入

### 5.1 模型定义

```python
class Author(models.Model):
    name = models.CharField(max_length=100, unique=True)

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["title"])]
```

- 关系：`ForeignKey`（多对一）、`OneToOneField`、`ManyToManyField`。
- `on_delete`：`CASCADE`（级联删）、`PROTECT`（禁止删）、`SET_NULL`（需 `null=True`）、`SET_DEFAULT`、`RESTRICT`。
- `related_name` 决定反向访问名：`author.books.all()`。
- 金额一律用 `DecimalField`，不要用 `FloatField`。

### 5.2 迁移

```bash
python manage.py makemigrations          # 比对模型 → 生成迁移文件（要提交进 git）
python manage.py migrate                 # 执行迁移
python manage.py sqlmigrate books 0001   # 查看迁移对应的 SQL
python manage.py showmigrations          # 查看已应用状态
```

数据迁移用 `migrations.RunPython(forward, backward)`，在函数里通过 `apps.get_model("books", "Book")` 取「历史版本」模型，**不要直接 import 当前模型**。

### 5.3 QuerySet 是惰性的

```python
qs = Book.objects.filter(price__gt=10).exclude(stock=0)   # 0 次查询
qs = qs.order_by("title")                                  # 仍是 0 次
titles = list(qs.values_list("title", flat=True))          # 这里才执行 1 次 SQL
```

触发求值的操作：迭代、`list()`、`len()`、切片带步长、`bool()`、`repr()`、`count()` / `exists()` / `first()` / `get()` 等。QuerySet 求值后会缓存结果，**同一个 QuerySet 对象**再次迭代不会重新查询。

### 5.4 查询表达式：字段查找、Q、F、聚合

```python
Book.objects.filter(title__icontains="django")             # LIKE，忽略大小写
Book.objects.filter(author__name="Ada")                     # 跨关系用双下划线
Book.objects.filter(Q(title__startswith="Django") | Q(stock=0))   # OR / NOT(~Q)
Book.objects.filter(pk=1).update(stock=F("stock") - 1)     # 在数据库侧计算，原子
Author.objects.annotate(n=Count("books"))                   # 每行附加聚合值（GROUP BY）
Book.objects.aggregate(avg=Avg("price"))                    # 整体聚合 → dict
```

- **F 表达式** 引用列值，在 SQL 里完成计算，避免「读到 Python 再写回」的竞态。
- `annotate` 是逐行附加，`aggregate` 是整体汇总。

### 5.5 N+1 问题：select_related 与 prefetch_related

```python
# 1 + N 次查询：每访问一次 b.author 就查一次
for b in Book.objects.all():
    b.author.name

# 1 次查询：SQL JOIN，适合 ForeignKey / OneToOne（「一」的那一端）
for b in Book.objects.select_related("author"):
    b.author.name

# 2 次查询：先查作者，再用 IN 一次查出所有书，Python 端拼装
# 适合 ManyToMany / 反向 ForeignKey（「多」的那一端）
for a in Author.objects.prefetch_related("books"):
    a.books.all()
```

本地测试用 `assertNumQueries` 实测：2 本书时，不优化 3 次、`select_related` 1 次、`prefetch_related` 2 次。

### 5.6 事务与并发

```python
from django.db import transaction

with transaction.atomic():                          # 块内全部成功才提交
    order = Order.objects.create(...)
    Book.objects.filter(pk=pk, stock__gt=0).update(stock=F("stock") - 1)
    transaction.on_commit(lambda: send_email.enqueue(order.id))   # 提交后才执行

with transaction.atomic():
    book = Book.objects.select_for_update().get(pk=pk)   # 行锁，必须在事务内
    book.stock -= 1
    book.save(update_fields=["stock"])
```

- 默认是 **autocommit**：每条 SQL 自动提交。`ATOMIC_REQUESTS=True` 可让每个请求包在一个事务里（简单但粒度粗）。
- `atomic` 可嵌套，内层变成 savepoint。
- 防超卖两种思路：**条件更新**（`filter(stock__gt=0).update(...)` 看返回行数）或 **悲观锁**（`select_for_update`）。

### 5.7 性能常用手段

| 手段 | 作用 |
|---|---|
| `only()` / `defer()` | 只取需要的列 |
| `values()` / `values_list()` | 返回 dict / tuple，跳过模型实例化 |
| `exists()` | 判断存在，比 `count() > 0` 快 |
| `bulk_create` / `bulk_update` | 批量写，一条 SQL |
| `iterator(chunk_size=...)` | 大结果集流式读取，不缓存 |
| `update()` / `delete()` on QuerySet | 一条 SQL 批量改，**不触发** `save()` 和信号 |
| `Index` / `db_index=True` | 给高频过滤 / 排序字段建索引 |

> **三框架对比 · ORM**
> - **相同**：Django ORM 与 SQLAlchemy 都有惰性查询、关联预加载、事务、迁移的概念。
> - **不同**：Django ORM 是 **Active Record** 风格（`book.save()`、`Book.objects.filter()`），与框架强绑定；SQLAlchemy 是 **Data Mapper + Unit of Work**（`session.add()` → `session.commit()`），表达力更强，Flask / FastAPI 都用它。
> - **对照**：`select_related` ≈ SQLAlchemy `joinedload`；`prefetch_related` ≈ `selectinload`；`F("stock") - 1` ≈ `Book.stock - 1`；`makemigrations` ≈ Alembic `revision --autogenerate`。

---

## 6. 常用方法速查

### 6.1 ORM

| 方法 | 返回 | 说明 |
|---|---|---|
| `objects.all()` / `filter()` / `exclude()` | QuerySet | 惰性 |
| `objects.get(**kw)` | 实例 | 0 条抛 `DoesNotExist`，多条抛 `MultipleObjectsReturned` |
| `objects.create(**kw)` | 实例 | 创建并保存 |
| `get_or_create(defaults=..., **kw)` | `(obj, created)` | 查不到就建 |
| `update_or_create(defaults=..., **kw)` | `(obj, created)` | 查到就改 |
| `first()` / `last()` | 实例或 None | 不抛异常 |
| `count()` / `exists()` | int / bool | 数据库侧计算 |
| `order_by("-f")` / `distinct()` | QuerySet | `-` 表示降序 |
| `values()` / `values_list(flat=True)` | QuerySet | dict / 扁平值 |
| `annotate()` / `aggregate()` | QuerySet / dict | 聚合 |
| `select_related()` / `prefetch_related()` | QuerySet | 防 N+1 |
| `in_bulk(ids)` | dict | `{pk: obj}` |
| `obj.save(update_fields=[...])` | None | 只更新指定列 |
| `obj.refresh_from_db()` | None | 重新从库里读 |
| 异步版：`aget` `acreate` `acount` `aexists` `afirst` `aupdate` `adelete` | 协程 | `await` 调用 |

### 6.2 视图与 HTTP

| 名称 | 说明 |
|---|---|
| `request.GET` / `request.POST` | QueryDict，表单 / 查询参数 |
| `request.body` | 原始字节，JSON 需 `json.loads` |
| `request.user` / `request.session` | 当前用户 / 会话 |
| `render(request, tpl, ctx)` | 渲染模板 |
| `redirect("app:name", pk=1)` | 重定向，可传 URL 名 |
| `JsonResponse(data, status=201)` | JSON 响应（非 dict 需 `safe=False`） |
| `HttpResponse(status=204)` | 原始响应 |
| `get_object_or_404(Model, **kw)` | 查不到抛 404 |
| `reverse("app:name", args=[...])` | 反解 URL |
| `@login_required` / `@require_POST` | 常用装饰器 |

### 6.3 manage.py

| 命令 | 说明 |
|---|---|
| `runserver` | 开发服务器（不要用于生产） |
| `makemigrations` / `migrate` | 迁移 |
| `shell` | 预加载模型的交互 shell |
| `dbshell` | 进数据库命令行 |
| `createsuperuser` | 建管理员 |
| `collectstatic` | 收集静态文件到 `STATIC_ROOT` |
| `test` | 跑测试 |
| `check --deploy` | 部署安全检查 |

---

## 7. 教程：从零写一个书店

目标：图书 CRUD + 搜索 + 购买扣库存（防超卖）+ 后台管理 + 请求耗时头。

### 7.1 配置（敏感项从环境变量读）

```python
# config/settings.py（节选）
import os

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")

INSTALLED_APPS = [
    # django.contrib.* ...
    "rest_framework",
    "books",
]

MIDDLEWARE = [
    # Django 默认中间件 ...
    "books.middleware.TimingMiddleware",
]
```

`dev-only-not-secret` 只是本地开发占位，生产环境必须通过 `DJANGO_SECRET_KEY` 注入真实随机值（`python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`）。

### 7.2 模型

见 [5.1](#51-模型定义)。写完执行 `makemigrations books && migrate`。

### 7.3 视图

```python
# books/views.py
import json

from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.http import require_http_methods

from .models import Author, Book


def book_to_dict(book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "author": book.author.name,
        "price": str(book.price),
        "stock": book.stock,
    }


@require_http_methods(["GET", "POST"])
def book_list(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        books = Book.objects.select_related("author")
        q = request.GET.get("q")
        if q:
            books = books.filter(title__icontains=q)
        return JsonResponse({"items": [book_to_dict(b) for b in books]})

    data = json.loads(request.body)
    author, _ = Author.objects.get_or_create(name=data["author"])
    book = Book.objects.create(
        title=data["title"], author=author, price=data["price"], stock=data.get("stock", 0)
    )
    return JsonResponse(book_to_dict(book), status=201)


class BookDetailView(View):
    def get(self, request: HttpRequest, pk: int) -> JsonResponse:
        book = get_object_or_404(Book.objects.select_related("author"), pk=pk)
        return JsonResponse(book_to_dict(book))

    def delete(self, request: HttpRequest, pk: int) -> HttpResponse:
        get_object_or_404(Book, pk=pk).delete()
        return HttpResponse(status=204)


def buy(request: HttpRequest, pk: int) -> JsonResponse:
    with transaction.atomic():
        updated = Book.objects.filter(pk=pk, stock__gt=0).update(stock=F("stock") - 1)
    if not updated:
        return JsonResponse({"detail": "sold out"}, status=409)
    return JsonResponse({"ok": True})


async def book_count(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"count": await Book.objects.acount()})
```

说明：

- 这里手写 JSON 视图是为了展示 Django 原生能力；真实 API 项目推荐用 [DRF](#8-django-rest-frameworkdrf)，校验、序列化、权限都省心。
- `buy` 用「带条件的 UPDATE + 看影响行数」实现防超卖，一条 SQL 原子完成。
- 204 响应必须没有 body，用 `HttpResponse(status=204)` 而不是 `JsonResponse({}, status=204)`。
- 示例中的 POST / DELETE 视图在浏览器表单场景下会受 CSRF 保护；纯 API 一般走 DRF 的 Token / JWT 认证。

### 7.4 路由

```python
# books/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, views

router = DefaultRouter()
router.register("books", api.BookViewSet)

app_name = "books"
urlpatterns = [
    path("books/", views.book_list, name="list"),
    path("books/count/", views.book_count, name="count"),
    path("books/<int:pk>/", views.BookDetailView.as_view(), name="detail"),
    path("books/<int:pk>/buy/", views.buy, name="buy"),
    path("api/", include(router.urls)),
]
```

### 7.5 Admin 后台

```python
# books/admin.py
from django.contrib import admin

from .models import Author, Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "price", "stock"]
    list_filter = ["author"]
    search_fields = ["title"]
    list_select_related = ["author"]      # 列表页防 N+1


admin.site.register(Author)
```

几行代码就得到带搜索、过滤、分页、增删改的后台。这是 Django 相对另外两个框架最大的生产力优势之一。

> **三框架对比 · 教程代码量**
> 同样的书店功能：Django 的模型 / 迁移 / 后台几乎零成本，但要理解 App、settings、URLconf 一整套约定；Flask 需要自己选 ORM、自己组织 Blueprint；FastAPI 需要自己写 Pydantic 模型和 DB 会话依赖，但换来自动校验和自动文档。

---

## 8. Django REST framework（DRF）

DRF 是 Django 写 API 的事实标准，提供：Serializer（校验 + 序列化）、ViewSet（CRUD 视图集）、Router（自动生成路由）、认证 / 权限 / 限流 / 分页 / 过滤、可浏览的 API 页面。

### 8.1 Serializer

```python
# books/serializers.py
from rest_framework import serializers

from .models import Author, Book


class BookSerializer(serializers.ModelSerializer):
    author = serializers.SlugRelatedField(slug_field="name", queryset=Author.objects.all())

    class Meta:
        model = Book
        fields = ["id", "title", "author", "price", "stock"]

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("price must be positive")
        return value
```

- 校验顺序：字段自身校验 → `validate_<field>()` → `validate(self, attrs)`（跨字段）。
- 用法：`s = BookSerializer(data=request.data); s.is_valid(raise_exception=True); s.save()`。
- 嵌套序列化时注意在 ViewSet 的 `queryset` 上做 `select_related` / `prefetch_related`，否则一样会 N+1。

### 8.2 ViewSet + Router

```python
# books/api.py
from rest_framework import permissions, viewsets

from .models import Book
from .serializers import BookSerializer


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author")
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
```

`router.register("books", BookViewSet)` 自动生成：

| 方法 | 路径 | 动作 |
|---|---|---|
| GET | `/api/books/` | list |
| POST | `/api/books/` | create |
| GET | `/api/books/{pk}/` | retrieve |
| PUT / PATCH | `/api/books/{pk}/` | update / partial_update |
| DELETE | `/api/books/{pk}/` | destroy |

自定义动作用 `@action(detail=True, methods=["post"])`。

### 8.3 全局配置

```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {"anon": "100/hour", "user": "1000/hour"},
}
```

OpenAPI 文档推荐 `drf-spectacular`；过滤推荐 `django-filter`；JWT 推荐 `djangorestframework-simplejwt`。

> **三框架对比 · 序列化与校验**
> - DRF `Serializer` ≈ Pydantic `BaseModel` ≈ Marshmallow `Schema`：都负责「入参校验 + 出参序列化」。
> - DRF 的 `validate_<field>` ≈ Pydantic 的 `@field_validator`；DRF 的 `validate()` ≈ Pydantic 的 `@model_validator`。
> - 不同点：Pydantic 基于类型注解，FastAPI 用它 **自动** 生成 OpenAPI；DRF 需要额外库才能得到同等质量的文档。DRF 的 `ModelSerializer` 能从模型自动推字段，这点 Pydantic 不具备（需要 SQLModel 之类的方案）。

---

## 9. 认证、权限与安全

### 9.1 认证体系

- `django.contrib.auth`：`User` 模型、密码哈希（默认 PBKDF2，可切换 Argon2）、登录登出视图、权限 / 组。
- **新项目一开始就自定义 User 模型**（`AUTH_USER_MODEL = "accounts.User"`），上线后再换代价极高。
- 获取用户模型用 `get_user_model()`，外键引用用 `settings.AUTH_USER_MODEL`。
- Session 认证：登录后服务端存 session，浏览器持有 `sessionid` cookie。

### 9.2 内置安全防护

| 威胁 | Django 的防护 |
|---|---|
| SQL 注入 | ORM 参数化；`raw()` / `extra()` 也要用参数而不是字符串拼接 |
| XSS | 模板自动转义 |
| CSRF | `CsrfViewMiddleware` + `{% csrf_token %}` |
| 点击劫持 | `XFrameOptionsMiddleware` |
| Host 头攻击 | `ALLOWED_HOSTS` |
| HTTPS | `SECURE_SSL_REDIRECT`、`SECURE_HSTS_SECONDS`、`SESSION_COOKIE_SECURE`、`CSRF_COOKIE_SECURE` |
| CSP | Django 6.0 起内置 `django.middleware.csp.ContentSecurityPolicyMiddleware`（之前需 `django-csp`） |

### 9.3 部署前检查

```bash
DJANGO_DEBUG=0 python manage.py check --deploy
```

实测它会报：`SECURE_HSTS_SECONDS` 未设置、`SECURE_SSL_REDIRECT` 未开、`SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` 未开、`SECRET_KEY` 太弱或带 `django-insecure-` 前缀、邮件仍是 console 后端等。上线前应清零。

> **三框架对比 · 安全默认值**
> - Django 默认开着 CSRF、XSS 转义、点击劫持防护，是三者中「默认最安全」的。
> - Flask 模板（Jinja2）默认转义，但 CSRF 需 Flask-WTF；session 是 **签名但不加密** 的 cookie。
> - FastAPI 面向 API，默认没有 CSRF（通常用 Bearer Token，不依赖 cookie）；认证靠 `fastapi.security` 工具 + 依赖注入自行组装。

---

## 10. 中间件与信号

### 10.1 自定义中间件

```python
# books/middleware.py
import time


class TimingMiddleware:
    def __init__(self, get_response):        # 进程启动时调用一次
        self.get_response = get_response

    def __call__(self, request):             # 每个请求调用
        start = time.perf_counter()
        response = self.get_response(request)        # 调用链中的下一层
        response["X-Elapsed-Ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
        return response
```

可选钩子：`process_view(request, view_func, args, kwargs)`、`process_exception(request, exception)`、`process_template_response(request, response)`。

### 10.2 信号

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Book)
def on_book_saved(sender, instance, created, **kwargs):
    if created:
        ...
```

- 常用：`pre_save` / `post_save` / `pre_delete` / `post_delete` / `m2m_changed` / `request_started` / `request_finished`。
- 信号是 **同步** 的，和发送方在同一个事务、同一个线程里执行；做耗时操作要丢给后台任务，且通常配合 `transaction.on_commit`。
- `QuerySet.update()` / `bulk_create()` **不会** 触发 `pre_save` / `post_save`。
- 信号让调用链变得隐式，团队里要克制使用；能显式调用就显式调用。

> **三框架对比 · 钩子机制**
> - Django：中间件类 + 信号。
> - Flask：`before_request` / `after_request` / `teardown_request` 钩子 + blinker 信号。
> - FastAPI：HTTP 中间件 + **依赖注入**（带 `yield` 的依赖可以做请求前后的资源管理）+ lifespan。

---

## 11. 异步支持

- Django 3.0 起支持 ASGI，3.1 起支持 `async def` 视图，4.1 起 ORM 提供异步接口（`aget` / `acreate` / `acount` / `async for` 迭代等）。
- 用 ASGI 服务器部署（`uvicorn config.asgi:application`）才能真正发挥异步视图的优势；在 WSGI 下 async 视图会为每个请求临时开一个事件循环，没有并发收益。
- 链路中若有同步中间件，Django 会在同步 / 异步之间来回切换线程，带来开销。
- **异步 ORM 的局限**：底层仍通过线程执行数据库调用；**事务在异步模式下不受支持**（没有 `aatomic`），需要事务时把整段逻辑写成同步函数，再用 `sync_to_async` 包起来调用。

```python
from asgiref.sync import sync_to_async

async def book_count(request):
    return JsonResponse({"count": await Book.objects.acount()})

@sync_to_async
def buy_sync(pk):
    with transaction.atomic():
        return Book.objects.filter(pk=pk, stock__gt=0).update(stock=F("stock") - 1)
```

> **三框架对比 · 异步**
> - Django：同步为主，异步是渐进加入的能力，ORM 异步 API 底层仍走线程。
> - Flask：`async def` 视图可用（需 `flask[async]`），但每个请求依然独占一个 WSGI worker，**不会带来并发提升**。
> - FastAPI：原生 ASGI，异步是一等公民；同步 `def` 路由会被扔进线程池执行。三者中只有 FastAPI 的异步是「从根上」设计的。

---

## 12. 后台任务

Django 6.0 起内置 **Tasks 框架**（`django.tasks`），统一了「定义任务 / 入队」的 API：

```python
# books/tasks.py
from django.tasks import task


@task
def notify_low_stock(book_id: int) -> str:
    return f"book {book_id} is low"

result = notify_low_stock.enqueue(7)     # 返回 TaskResult
```

注意：

- 内置后端只有 `ImmediateBackend`（当前进程立即同步执行，默认）和 `DummyBackend`（只记录不执行，测试用）。实测 `enqueue` 后状态直接是 `SUCCESSFUL`，返回值为 `"book 7 is low"`——**它并没有真正异步**。
- 真正放到 worker 里跑，需要第三方后端（如 `django-tasks` 的数据库后端），或者继续用 **Celery** / RQ / Dramatiq。
- 与事务配合：`transaction.on_commit(lambda: notify_low_stock.enqueue(book.id))`，避免事务回滚了任务却已执行。

Celery 经典搭配：Redis / RabbitMQ 做 broker，`celery -A config worker`，定时任务用 `celery beat`。

> **三框架对比 · 后台任务**
> - Django：6.0+ 有统一 API，生产仍需外部 worker（Celery 最常见）。
> - Flask：没有内置，直接用 Celery / RQ。
> - FastAPI：内置 `BackgroundTasks`，在 **响应发出后、同一进程内** 执行，适合发邮件、写日志这类轻任务；重任务同样要 Celery / arq。

---

## 13. 测试

```python
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class BookTests(TestCase):
    @classmethod
    def setUpTestData(cls):                       # 整个类只建一次数据
        cls.ada = Author.objects.create(name="Ada")
        cls.bob = Author.objects.create(name="Bob")
        Book.objects.create(title="Django Basics", author=cls.ada, price="30.00", stock=1)
        Book.objects.create(title="Flask Notes", author=cls.bob, price="20.00", stock=0)

    def test_list_and_filter(self):
        resp = self.client.get(reverse("books:list"), {"q": "django"})
        self.assertEqual([b["title"] for b in resp.json()["items"]], ["Django Basics"])
        self.assertIn("X-Elapsed-Ms", resp)

    def test_select_related_avoids_n_plus_one(self):
        with self.assertNumQueries(1):
            [b.author.name for b in Book.objects.select_related("author")]
        with self.assertNumQueries(3):
            [b.author.name for b in Book.objects.all()]

    def test_buy_uses_f_expression(self):
        book = Book.objects.get(title="Django Basics")
        self.assertEqual(self.client.post(reverse("books:buy", args=[book.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse("books:buy", args=[book.pk])).status_code, 409)

    def test_drf_viewset(self):
        api = APIClient()
        self.assertEqual(api.post("/api/books/", {"title": "X", "author": "Ada", "price": "1"}).status_code, 403)
        user = User.objects.create_user("u", password="pw-for-test-only")
        api.force_authenticate(user)
        self.assertEqual(api.post("/api/books/", {"title": "X", "author": "Ada", "price": "0"}).status_code, 400)
```

- `TestCase` 每个测试包在事务里，结束时回滚，测试之间互不影响；测试库是独立创建的。
- `SimpleTestCase`（不碰数据库）、`TransactionTestCase`（需要测真实提交 / `on_commit` 时用）、`LiveServerTestCase`（配合 Selenium / Playwright）。
- `assertNumQueries` 是防 N+1 回归的利器。
- 团队里常用 `pytest-django` + `factory_boy`，写法更简洁。

本地验证结果：`python manage.py test books` → **11 tests OK**。

> **三框架对比 · 测试**
> - **相同**：三者都提供不启动真实服务器的测试客户端（Django `Client`、Flask `test_client()`、FastAPI `TestClient`）。
> - **不同**：Django 自动建测试库并按测试回滚；Flask / FastAPI 要自己用 fixture 建表、清理。FastAPI 独有的 `dependency_overrides` 可以一行替换数据库会话、配置、鉴权，是三者中最方便打桩的。

---

## 14. 工程实践

### 14.1 目录组织

```text
project/
├── config/
│   ├── settings/
│   │   ├── base.py         # 公共配置
│   │   ├── dev.py          # from .base import *; DEBUG = True
│   │   └── prod.py         # 安全相关配置全开
│   ├── urls.py  asgi.py  wsgi.py
├── apps/
│   ├── accounts/           # 自定义 User
│   ├── books/
│   │   ├── models.py  admin.py  urls.py
│   │   ├── views.py / api.py / serializers.py
│   │   ├── services.py     # 业务逻辑（写操作、跨模型流程）
│   │   ├── selectors.py    # 复杂查询
│   │   └── tests/
├── templates/  static/
└── manage.py
```

- **胖模型、瘦视图** 是老建议；业务复杂后更推荐抽出 `services.py`，视图只负责 HTTP 适配，便于复用和测试。
- 配置按环境拆分，敏感值一律走环境变量（`django-environ` 或直接 `os.environ`），`.env` 不进 git。

### 14.2 数据库

- 生产用 PostgreSQL；`CONN_MAX_AGE=60` + `CONN_HEALTH_CHECKS=True` 复用连接；连接很多时前置 PgBouncer。
- 迁移文件进 git，部署流水线里执行 `migrate`；大表加字段 / 加索引注意锁表，PostgreSQL 可用 `AddIndexConcurrently`。

### 14.3 缓存

```python
from django.core.cache import cache
from django.views.decorators.cache import cache_page

@cache_page(60)                 # 整页缓存
def book_list(request): ...

cache.get_or_set("hot_books", lambda: list(Book.objects.values("id", "title")[:10]), 300)
```

后端用 Redis（`django.core.cache.backends.redis.RedisCache`，4.0 起内置）。进程内用 `LocMemCache`，Memcached 用 `PyMemcacheCache`。和 Flask / FastAPI 的 SQLAlchemy、Peewee、cachetools 怎么对应，见 [常用第三方库](./libraries.md)。

### 14.4 部署

```bash
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# 同步（WSGI）
gunicorn config.wsgi:application --workers 4 --bind 0.0.0.0:8000
# 异步（ASGI），需 pip install uvicorn-worker（旧的 uvicorn.workers 已弃用）
gunicorn config.asgi:application -k uvicorn_worker.UvicornWorker --workers 4
```

- Worker 数常见经验值 `2 × CPU + 1`，再按压测调整。
- 静态文件交给 Nginx / CDN，或用 WhiteNoise 直接由应用服务。
- 容器化时：非 root 用户运行、健康检查接口、日志打到 stdout。

### 14.5 可观测性

- `LOGGING` 字典配置，结构化日志（JSON）。
- `django-debug-toolbar`（开发期看 SQL）、Sentry（异常）、OpenTelemetry（链路追踪）。

> **三框架对比 · 工程结构**
> - Django：天然按 App 切分，有统一约定，大团队协作成本低。
> - Flask：靠 **应用工厂 + Blueprint** 自己搭，结构因团队而异。
> - FastAPI：靠 `APIRouter` 按领域拆分，`schemas` / `deps` / `services` 的分层是社区约定而非框架强制。

---

## 15. 面试题与参考回答

**Q1：Django 一个请求从进来到返回经历了什么？**
WSGI/ASGI 服务器把请求交给 Django 的 Handler，构造 `HttpRequest`；按 `MIDDLEWARE` 顺序执行中间件的请求阶段；按 `ROOT_URLCONF` 匹配 URL 找到视图；视图执行业务（ORM、模板）返回 `HttpResponse`；再逆序经过中间件的响应阶段；最后交回服务器发给客户端。异常会经过 `process_exception` 和异常处理逻辑转成 404 / 500。

**Q2：`select_related` 和 `prefetch_related` 的区别？**
`select_related` 用 SQL JOIN 在一条查询里把关联对象取回来，适合外键和一对一这种「指向单个对象」的关系。`prefetch_related` 先查主表，再用 `IN` 单独查关联表，在 Python 里拼装，适合多对多和反向外键这种「一对多」关系，避免 JOIN 造成行数膨胀。两者都是为了解决 N+1 问题。

**Q3：QuerySet 什么时候真正查询数据库？**
QuerySet 是惰性的，`filter` / `exclude` / `order_by` 只是在构造 SQL。迭代、`list()`、`len()`、`bool()`、切片带步长、`get()`、`count()`、`exists()` 等操作才触发查询。求值后结果缓存在该 QuerySet 上，重复迭代不再查库；但每次链式调用都会产生新 QuerySet，缓存不共享。

**Q4：如何防止超卖？**
两种方法。一是条件更新：`filter(pk=pk, stock__gt=0).update(stock=F("stock") - 1)`，数据库单条语句原子执行，根据影响行数判断成功与否。二是悲观锁：在 `transaction.atomic()` 里 `select_for_update()` 锁住行再修改。高并发场景还可以把库存预扣放到 Redis，用 Lua 保证原子性，再异步落库。

**Q5：F 表达式有什么用？**
在数据库层面引用字段值进行计算，生成 `SET stock = stock - 1` 这样的 SQL，避免「先读到 Python，再写回」导致的竞态条件，同时少一次查询。也可以用在 `filter(stock__lt=F("min_stock"))` 这类字段间比较中。

**Q6：Django 的中间件执行顺序？**
请求阶段按 `MIDDLEWARE` 列表从上到下执行，响应阶段从下到上执行，像洋葱。某个中间件提前返回响应，后面的中间件和视图不会执行，但它前面的中间件仍然会处理响应。顺序有依赖，比如 `AuthenticationMiddleware` 必须在 `SessionMiddleware` 之后。

**Q7：CSRF 的原理和 Django 怎么防？**
CSRF 是攻击者诱导已登录用户的浏览器向目标站点发请求，借用用户的 cookie。Django 给每个会话下发一个 CSRF token（cookie 中存一份），表单提交或 AJAX 请求必须带上这个 token（隐藏字段或 `X-CSRFToken` 头），中间件比对通过才放行。攻击者的页面无法读取目标站点的 cookie，也就拿不到 token。

**Q8：信号有什么坑？**
信号是同步执行的，和业务在同一事务里，耗时操作会拖慢请求；`update()` / `bulk_create()` 不触发 `save` 相关信号；调用关系隐式，排查困难。需要异步副作用时，用 `transaction.on_commit` 加后台任务。

**Q9：Django 能做高并发吗？异步支持到什么程度？**
Django 主要通过多进程（gunicorn workers）+ 缓存 + 数据库优化来扛并发，这对大多数业务足够。从 3.x 开始支持 ASGI 和异步视图，ORM 也有异步接口，但 ORM 底层仍通过线程执行，异步上下文中不支持事务，生态中很多库仍是同步的。如果核心诉求是大量长连接、流式输出、IO 密集的高并发 API，FastAPI 更合适；也可以 Django 做主站 + FastAPI 做特定服务。

**Q10：Django ORM 和 SQLAlchemy 的区别？**
Django ORM 是 Active Record 风格，模型自己负责持久化（`obj.save()`），API 简洁，与 Admin、Form、DRF 深度集成，但复杂 SQL 表达力有限、脱离 Django 难用。SQLAlchemy 是 Data Mapper + Unit of Work，通过 Session 统一管理对象状态和提交，表达力强、可独立使用，学习曲线更陡。

**Q11：为什么要一开始就自定义 User 模型？**
`AUTH_USER_MODEL` 在第一次迁移后被大量外键引用，中途更换需要改迁移和数据，非常痛苦。一开始继承 `AbstractUser` 建一个空的自定义模型，以后加字段只是普通迁移。

**Q12：`DEBUG=True` 放到生产会怎样？**
报错页会暴露源码片段、settings（部分脱敏）、SQL、环境信息；Django 会在内存里记录所有 SQL，长期运行导致内存增长；静态文件处理方式也不同。必须关闭，并配好 `ALLOWED_HOSTS`。

**Q13：Django、Flask、FastAPI 怎么选？**
业务模型复杂、需要后台和用户体系、追求交付速度选 Django；轻量服务、需要高度定制或团队想自己挑组件选 Flask；以 API 为主、追求高并发和自动文档、类型安全，或者做 LLM 流式服务选 FastAPI。三者不是互斥的，常见组合是 Django 做管理后台，FastAPI 做对外高并发接口。

---

## 16. 常见坑

| 坑 | 正确做法 |
|---|---|
| 循环里访问外键导致 N+1 | `select_related` / `prefetch_related`，用 `assertNumQueries` 守住 |
| `FloatField` 存金额 | `DecimalField` |
| 用 `count() > 0` 判断存在 | `exists()` |
| 在 Python 里 `obj.stock -= 1; obj.save()` 并发扣库存 | `F` 表达式或 `select_for_update` |
| 直接 import 模型写数据迁移 | `apps.get_model()` |
| 以为 `update()` 会触发 `save()` / 信号 | 不会，需要时显式处理 |
| 在 async 视图里直接调同步 ORM | 用 `a*` 方法或 `sync_to_async`，否则抛 `SynchronousOnlyOperation` |
| 以为 `django.tasks` 默认就是异步执行 | 默认 `ImmediateBackend` 是同步的，生产要配真实后端 |
| `SECRET_KEY` 写死在代码里 | 环境变量 / 密钥管理服务 |
| `runserver` 上生产 | gunicorn / uvicorn |
