"""Flask-SQLAlchemy 3.x + SQLAlchemy 2.x：模型、select 查询、防 N+1、原子扣库存。

运行：pip install flask-sqlalchemy && python sqlalchemy_crud.py
"""

from decimal import Decimal

from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, Numeric, String, event
from sqlalchemy.orm import DeclarativeBase, Mapped, joinedload, mapped_column, relationship


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


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

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "author": self.author.name,
                "price": str(self.price), "stock": self.stock}


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
db.init_app(app)


@app.get("/books/")
def list_books():
    stmt = db.select(Book).options(joinedload(Book.author)).order_by(Book.id)   # JOIN 取作者
    if q := request.args.get("q"):
        stmt = stmt.where(Book.title.ilike(f"%{q}%"))
    return {"items": [b.to_dict() for b in db.session.execute(stmt).scalars()]}


@app.get("/books/<int:book_id>")
def get_book(book_id: int):
    return db.get_or_404(Book, book_id).to_dict()       # 查不到直接 404


@app.post("/books/<int:book_id>/buy")
def buy(book_id: int):
    result = db.session.execute(                        # UPDATE ... WHERE stock > 0
        db.update(Book).where(Book.id == book_id, Book.stock > 0).values(stock=Book.stock - 1)
    )
    db.session.commit()
    if result.rowcount == 0:
        return jsonify(detail="sold out"), 409
    return {"ok": True}


if __name__ == "__main__":
    with app.app_context():                             # db.session 绑定在应用上下文上
        db.create_all()                                 # 真实项目用 Flask-Migrate：flask db upgrade
        ada = Author(name="Ada")
        db.session.add_all([
            Book(title="Flask Notes", author=ada, price=Decimal("20.00"), stock=1),
            Book(title="SQLAlchemy", author=ada, price=Decimal("35.00"), stock=0),
            Book(title="Jinja", author=Author(name="Bob"), price=Decimal("15.00"), stock=3),
        ])
        db.session.commit()

        statements: list[str] = []
        event.listen(db.engine, "before_cursor_execute",
                     lambda *args: statements.append(args[2]))

        client = app.test_client()
        assert [b["title"] for b in client.get("/books/?q=flask").get_json()["items"]] == ["Flask Notes"]
        statements.clear()
        client.get("/books/")
        assert len(statements) == 1                     # joinedload：3 本书 1 条 SQL

        statements.clear()
        db.session.expire_all()
        [b.author.name for b in db.session.execute(db.select(Book)).scalars()]
        assert len(statements) == 3                     # 懒加载：1 条查书 + 2 个作者各 1 条

        assert client.get("/books/99").status_code == 404
        assert client.post("/books/1/buy").status_code == 200
        assert client.post("/books/1/buy").status_code == 409
        assert db.session.get(Book, 1).stock == 0
        print("joinedload=1 SQL, lazy=3 SQL, buy → 200 then 409")
