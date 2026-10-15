"""Peewee：轻量 ORM。查询写法接近 Django，但自己管连接和事务。

运行：pip install peewee && python peewee_orm.py
Flask / FastAPI 都能直接用；Django 项目通常继续用自带 ORM，不必再叠一层 Peewee。
"""

import peewee as pw

# DatabaseProxy：模型先定义，真正的数据库稍后 initialize（测试换 sqlite、生产换 postgres）
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


class CountingDB(pw.SqliteDatabase):
    """数 SELECT 条数，用来看 N+1。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.selects = 0

    def execute_sql(self, sql, params=None):
        if str(sql).lstrip()[:6].upper() == "SELECT":
            self.selects += 1
        return super().execute_sql(sql, params)


def selects_for(fn) -> int:
    before = db.selects
    fn()
    return db.selects - before


if __name__ == "__main__":
    db.initialize(CountingDB(":memory:"))
    db.connect()
    db.create_tables([Author, Book])

    ada = Author.create(name="Ada")
    bob = Author.get_or_create(name="Bob")[0]          # (instance, created)
    Book.create(title="Peewee Notes", price="18.50", stock=2, author=ada)
    Book.create(title="SQLAlchemy", price="30.00", stock=0, author=ada)
    Book.create(title="Jinja", price="15.00", stock=4, author=bob)

    # 1) 惰性：select() 先不查，迭代时才查
    query = Book.select().where(Book.price > 10, Book.stock > 0).order_by(Book.title)
    assert selects_for(lambda: None) == 0
    titles = [b.title for b in query]
    assert titles == ["Jinja", "Peewee Notes"]

    # 2) 参数化：title.contains 生成 LIKE ?，不会把输入拼进 SQL
    found = Book.select().where(Book.title.contains("pee")).get()
    assert found.author.name == "Ada"

    # 3) N+1：直接点外键是 1 + N；join 时把 Author 也 select 出来才是 1 条；prefetch 是 2 条
    lazy = selects_for(lambda: [b.author.name for b in Book.select()])
    joined = selects_for(lambda: [b.author.name for b in Book.select(Book, Author).join(Author)])
    prefetched = selects_for(
        lambda: [len(a.books) for a in pw.prefetch(Author.select(), Book.select())]
    )
    assert (lazy, joined, prefetched) == (4, 1, 2)

    # 4) 条件更新：一条 SQL，WHERE 与 SET 同时执行
    with db.atomic():
        updated = (
            Book.update(stock=Book.stock - 1)
            .where((Book.id == found.id) & (Book.stock > 0))
            .execute()
        )
    assert updated == 1
    assert found.stock == 2                       # UPDATE 不刷新已经取出来的对象
    assert Book.get_by_id(found.id).stock == 1
    try:
        Book.get_by_id(999)
    except Book.DoesNotExist:
        pass

    # 原子块里抛异常会回滚
    try:
        with db.atomic():
            Book.create(title="rolled back", price="1.00", stock=1, author=ada)
            raise RuntimeError("payment failed")
    except RuntimeError:
        pass
    assert Book.select().where(Book.title == "rolled back").count() == 0

    print(f"lazy={lazy}  join={joined}  prefetch={prefetched}  stock=1")
    db.close()
