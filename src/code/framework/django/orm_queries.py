"""Django ORM：模型、惰性 QuerySet、Q / F 表达式、聚合。

运行：python orm_queries.py（内存 SQLite，不需要迁移文件）
"""

import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=["__main__"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
django.setup()

from django.db import connection, models
from django.db.models import Avg, Count, F, Q
from django.test.utils import CaptureQueriesContext


class Author(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        app_label = "__main__"


class Book(models.Model):
    title = models.CharField(max_length=200)
    # related_name 决定反向访问名：author.books.all()
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    price = models.DecimalField(max_digits=8, decimal_places=2)   # 金额用 Decimal，不用 Float
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "__main__"
        ordering = ["id"]
        indexes = [models.Index(fields=["title"])]


def create_tables() -> None:
    # 真实项目用 makemigrations + migrate；单文件演示直接建表
    with connection.schema_editor() as editor:
        editor.create_model(Author)
        editor.create_model(Book)


if __name__ == "__main__":
    create_tables()
    ada = Author.objects.create(name="Ada")
    bob, created = Author.objects.get_or_create(name="Bob")      # 查不到就建
    assert created
    Book.objects.create(title="Django Basics", author=ada, price="30.00", stock=1)
    Book.objects.create(title="Django ORM", author=ada, price="40.00", stock=0)
    Book.objects.create(title="Flask Notes", author=bob, price="20.00", stock=5)

    # 1) QuerySet 是惰性的：链式调用只是在拼 SQL
    with CaptureQueriesContext(connection) as ctx:
        qs = Book.objects.filter(price__gt=10).exclude(stock=0).order_by("title")
    assert len(ctx) == 0
    with CaptureQueriesContext(connection) as ctx:
        titles = list(qs.values_list("title", flat=True))         # 求值：这里才查库
    assert titles == ["Django Basics", "Flask Notes"] and len(ctx) == 1

    # 2) 字段查找：双下划线跨关系、忽略大小写
    assert Book.objects.filter(author__name="Ada", title__icontains="orm").count() == 1

    # 3) Q：组合 OR / NOT
    assert Book.objects.filter(Q(title__startswith="Flask") | Q(stock=0)).count() == 2
    assert Book.objects.filter(~Q(author=ada)).count() == 1

    # 4) F：在数据库侧引用列值，生成 SET stock = stock + 10
    Book.objects.filter(author=bob).update(stock=F("stock") + 10)
    assert Book.objects.get(title="Flask Notes").stock == 15

    # 5) annotate 逐行附加聚合值；aggregate 整体汇总成 dict
    per_author = dict(Author.objects.annotate(n=Count("books")).values_list("name", "n"))
    assert per_author == {"Ada": 2, "Bob": 1}
    assert Book.objects.aggregate(avg=Avg("price"))["avg"] == 30

    # 6) get：0 条抛 DoesNotExist，多条抛 MultipleObjectsReturned；first() 不抛
    try:
        Book.objects.get(title="nope")
    except Book.DoesNotExist:
        pass
    assert Book.objects.filter(title="nope").first() is None
    assert Book.objects.filter(stock=0).exists()

    print("SQL:", str(qs.query)[:80], "...")
