"""N+1 问题：select_related（JOIN）与 prefetch_related（IN 二次查询）。

运行：python n_plus_one.py
用 CaptureQueriesContext 数清楚每种写法到底发了几条 SQL。
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
from django.test.utils import CaptureQueriesContext


class Author(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "__main__"


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")

    class Meta:
        app_label = "__main__"


def count_queries(fn) -> int:
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx)


if __name__ == "__main__":
    with connection.schema_editor() as editor:
        editor.create_model(Author)
        editor.create_model(Book)
    for name in ["Ada", "Bob", "Cy"]:
        a = Author.objects.create(name=name)
        Book.objects.create(title=f"{name} 1", author=a)
        Book.objects.create(title=f"{name} 2", author=a)

    # 1) 不优化：1 条查书 + 每本书访问 author 再查 1 条 → 1 + 6
    naive = count_queries(lambda: [b.author.name for b in Book.objects.all()])

    # 2) select_related：SQL JOIN，一条搞定。适合 ForeignKey / OneToOne（指向「一」）
    joined = count_queries(
        lambda: [b.author.name for b in Book.objects.select_related("author")]
    )

    # 3) prefetch_related：先查作者，再 WHERE author_id IN (...) 一次查出所有书，
    #    Python 端拼装。适合反向 ForeignKey / ManyToMany（指向「多」）
    prefetched = count_queries(
        lambda: [len(a.books.all()) for a in Author.objects.prefetch_related("books")]
    )

    # 4) 反例：prefetch 之后又 filter，会绕过缓存，每个作者再查一次 → 2 + 3
    broken = count_queries(
        lambda: [a.books.filter(title__endswith="1").count()
                 for a in Author.objects.prefetch_related("books")]
    )

    print(f"all()={naive}  select_related={joined}  "
          f"prefetch_related={prefetched}  prefetch+filter={broken}")
    assert (naive, joined, prefetched, broken) == (7, 1, 2, 5)
