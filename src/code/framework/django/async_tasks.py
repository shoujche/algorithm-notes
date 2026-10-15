"""Django 的异步视图、异步 ORM 与内置 Tasks 框架（Django 6.0+）。

运行：python async_tasks.py
"""

import asyncio
import os
import tempfile

import django
from django.conf import settings

settings.configure(
    DEBUG=True,
    SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret"),
    ALLOWED_HOSTS=["testserver"],
    ROOT_URLCONF=__name__,
    INSTALLED_APPS=["__main__"],
    # 异步 ORM 实际在工作线程里查库；内存 SQLite 每个线程一个独立库，所以这里用临时文件
    DATABASES={"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(tempfile.mkdtemp(), "demo.sqlite3"),
    }},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    # 不配置时默认就是 ImmediateBackend：enqueue 时在当前进程同步执行
    TASKS={"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}},
)
django.setup()

from asgiref.sync import sync_to_async
from django.core.exceptions import SynchronousOnlyOperation
from django.db import connection, models, transaction
from django.http import JsonResponse
from django.tasks import task
from django.test import AsyncClient
from django.urls import path


class Book(models.Model):
    title = models.CharField(max_length=200)

    class Meta:
        app_label = "__main__"


# ---------------------------------------------------------------------------
# 1) 异步视图 + 异步 ORM：aget / acreate / acount / afirst / async for ...
# ---------------------------------------------------------------------------
async def book_count(request):
    return JsonResponse({"count": await Book.objects.acount()})


urlpatterns = [path("count/", book_count)]


# ---------------------------------------------------------------------------
# 2) 异步上下文里没有 aatomic：需要事务时写成同步函数，再 sync_to_async 包一层
# ---------------------------------------------------------------------------
@sync_to_async
def create_two(title: str) -> None:
    with transaction.atomic():
        Book.objects.create(title=f"{title} 1")
        Book.objects.create(title=f"{title} 2")


# ---------------------------------------------------------------------------
# 3) 内置 Tasks：统一的「定义 / 入队」API，真正后台执行要配第三方后端或用 Celery
# ---------------------------------------------------------------------------
@task
def notify_low_stock(book_id: int) -> str:
    return f"book {book_id} is low"


async def main() -> None:
    await create_two("Async")
    resp = await AsyncClient().get("/count/")
    assert resp.json() == {"count": 2}

    try:
        Book.objects.count()                    # 在事件循环里直接调同步 ORM
    except SynchronousOnlyOperation:
        print("sync ORM in async context → SynchronousOnlyOperation")

    first = await Book.objects.order_by("id").afirst()
    titles = [b.title async for b in Book.objects.order_by("id")]
    assert first.title == "Async 1" and titles == ["Async 1", "Async 2"]


if __name__ == "__main__":
    with connection.schema_editor() as editor:
        editor.create_model(Book)
    asyncio.run(main())

    result = notify_low_stock.enqueue(7)
    # ImmediateBackend：入队即执行完毕，并不是真正的异步
    assert result.status.name == "SUCCESSFUL"
    assert result.return_value == "book 7 is low"
    print("task:", result.status.name, result.return_value)
