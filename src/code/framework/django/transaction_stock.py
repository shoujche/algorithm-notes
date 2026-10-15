"""事务与防超卖：transaction.atomic、F 条件更新、on_commit。

运行：python transaction_stock.py
"""

import django
from django.conf import settings

settings.configure(
    INSTALLED_APPS=["__main__"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
django.setup()

from django.db import connection, models, transaction
from django.db.models import F


class Book(models.Model):
    title = models.CharField(max_length=200)
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "__main__"


class Order(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    class Meta:
        app_label = "__main__"


sent: list[int] = []


def buy(book_id: int) -> bool:
    """条件更新：WHERE stock > 0 与 SET stock = stock - 1 在一条 SQL 里原子完成。"""
    with transaction.atomic():
        updated = Book.objects.filter(pk=book_id, stock__gt=0).update(stock=F("stock") - 1)
        if not updated:                    # 影响 0 行 = 已售罄，调用方返回 409
            return False
        order = Order.objects.create(book_id=book_id)
        # 事务提交后才执行；若回滚则不会执行，避免「订单没了邮件却发了」
        transaction.on_commit(lambda: sent.append(order.id))
    return True


def buy_with_lock(book_id: int) -> bool:
    """悲观锁写法：select_for_update 必须在事务里（SQLite 会忽略锁，PostgreSQL / MySQL 生效）。"""
    with transaction.atomic():
        book = Book.objects.select_for_update().get(pk=book_id)
        if book.stock == 0:
            return False
        book.stock -= 1
        book.save(update_fields=["stock"])     # 只更新这一列
    return True


if __name__ == "__main__":
    with connection.schema_editor() as editor:
        editor.create_model(Book)
        editor.create_model(Order)
    book = Book.objects.create(title="Django", stock=2)

    assert buy(book.pk) is True
    assert buy_with_lock(book.pk) is True
    assert buy(book.pk) is False              # 第三次：库存 0，不会扣成负数
    book.refresh_from_db()
    assert book.stock == 0 and sent == [1]

    # atomic 块内抛异常 → 整块回滚
    try:
        with transaction.atomic():
            Order.objects.create(book=book)
            raise RuntimeError("payment failed")
    except RuntimeError:
        pass
    assert Order.objects.count() == 1

    # 嵌套 atomic = savepoint：内层回滚不影响外层
    with transaction.atomic():
        Order.objects.create(book=book)
        try:
            with transaction.atomic():
                Order.objects.create(book=book)
                raise ValueError
        except ValueError:
            pass
    assert Order.objects.count() == 2

    print("stock:", book.stock, "orders:", Order.objects.count(), "notified:", sent)
