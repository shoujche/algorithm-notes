"""同一个书店接口 · Flask 版：创建（校验）/ 查询（404）/ 购买（409 防超卖）。

运行：pip install flask-sqlalchemy && python bookshop_flask.py
"""

from decimal import Decimal, InvalidOperation

from flask import Flask, abort, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from werkzeug.exceptions import HTTPException


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)                # ORM：扩展提供，session 绑在应用上下文


class Book(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    stock: Mapped[int] = mapped_column(default=0)

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "price": str(self.price), "stock": self.stock}


app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
db.init_app(app)


@app.errorhandler(HTTPException)                 # 默认错误页是 HTML，API 要改成 JSON
def json_error(err: HTTPException):
    return jsonify(detail=err.description), err.code


@app.post("/books/")                             # 路由：装饰器写在视图上
def create_book():
    data = request.get_json(silent=True) or {}   # request 是上下文全局代理（隐式）
    errors = {}                                  # 校验：框架不管，手写或接 Marshmallow / Pydantic
    if not data.get("title"):
        errors["title"] = "required"
    try:
        if Decimal(str(data.get("price"))) <= 0:
            errors["price"] = "must be > 0"
    except InvalidOperation:
        errors["price"] = "invalid"
    if errors:
        return {"detail": errors}, 400
    book = Book(title=data["title"], price=Decimal(str(data["price"])), stock=data.get("stock", 0))
    db.session.add(book)
    db.session.commit()
    return book.to_dict(), 201


@app.get("/books/<int:pk>")
def get_book(pk: int):
    return db.get_or_404(Book, pk).to_dict()


@app.post("/books/<int:pk>/buy")
def buy(pk: int):
    result = db.session.execute(
        db.update(Book).where(Book.id == pk, Book.stock > 0).values(stock=Book.stock - 1)
    )
    db.session.commit()
    if result.rowcount == 0:
        abort(409, description="sold out")
    return {"ok": True}


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        c = app.test_client()

        assert c.post("/books/", json={"title": "Flask", "price": "30", "stock": 1}).status_code == 201
        bad = c.post("/books/", json={"title": "", "price": "0"})
        assert bad.status_code == 400 and set(bad.get_json()["detail"]) == {"title", "price"}
        assert c.get("/books/1").get_json()["price"] == "30.00"
        assert c.get("/books/99").status_code == 404
        assert [c.post("/books/1/buy").status_code for _ in range(2)] == [200, 409]
        print("flask: 201 / 400 / 404 / 200 → 409")
