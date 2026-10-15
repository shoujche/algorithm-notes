"""同一个书店接口 · FastAPI 版：创建（校验）/ 查询（404）/ 购买（409 防超卖）。

运行：pip install "fastapi[standard]" sqlalchemy && python bookshop_fastapi.py
"""

from collections.abc import Iterator
from decimal import Decimal
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Numeric, String, create_engine, update
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Book(Base):                                # ORM：直接用 SQLAlchemy
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    stock: Mapped[int] = mapped_column(default=0)


class BookIn(BaseModel):                         # 校验：声明类型 + 约束，失败自动 422
    title: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    stock: int = Field(default=0, ge=0)


class BookOut(BookIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


def get_session() -> Iterator[Session]:          # 依赖注入：会话显式出现在参数里
    with SessionLocal() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
app = FastAPI()


@app.post("/books/", response_model=BookOut, status_code=201)
def create_book(data: BookIn, session: SessionDep):     # 请求体由类型注解声明
    book = Book(**data.model_dump())
    session.add(book)
    session.commit()
    return book


@app.get("/books/{pk}", response_model=BookOut)
def get_book(pk: int, session: SessionDep):
    if (book := session.get(Book, pk)) is None:
        raise HTTPException(404, "book not found")
    return book


@app.post("/books/{pk}/buy")
def buy(pk: int, session: SessionDep):
    result = session.execute(
        update(Book).where(Book.id == pk, Book.stock > 0).values(stock=Book.stock - 1)
    )
    session.commit()
    if result.rowcount == 0:
        raise HTTPException(409, "sold out")
    return {"ok": True}


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    c = TestClient(app)

    assert c.post("/books/", json={"title": "FastAPI", "price": "30", "stock": 1}).status_code == 201
    bad = c.post("/books/", json={"title": "", "price": "0"})
    assert bad.status_code == 422
    assert {e["loc"][-1] for e in bad.json()["detail"]} == {"title", "price"}
    assert c.get("/books/1").json()["price"] == "30.00"
    assert c.get("/books/99").status_code == 404
    assert [c.post("/books/1/buy").status_code for _ in range(2)] == [200, 409]
    assert "/books/{pk}" in c.get("/openapi.json").json()["paths"]   # 文档自动生成
    print("fastapi: 201 / 422 / 404 / 200 → 409")
