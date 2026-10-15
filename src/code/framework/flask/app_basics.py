"""Flask 基础：路由、取参数、视图返回值、url_for、abort。

运行：python app_basics.py（用 test_client 演示，不启动服务器）
开发时启动：flask --app app_basics run --debug（debug 绝不能用于生产）
"""

from flask import Flask, abort, make_response, redirect, request, url_for

app = Flask(__name__)


# ---------------------------------------------------------------------------
# 1) 路由：@app.get / @app.post 是 @app.route(methods=[...]) 的简写
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return "<h1>hello</h1>"                      # str → HTML，200


@app.get("/books/<int:book_id>")                 # 转换器：string int float path uuid
def get_book(book_id: int):
    if book_id > 100:
        abort(404, description="book not found")  # 抛 HTTPException，后续代码不执行
    return {"id": book_id}                       # dict → 自动 JSON


@app.get("/search")
def search():
    q = request.args.get("q", "")                # 查询参数（MultiDict）
    page = request.args.get("page", 1, type=int)  # 带类型转换，失败用默认值
    return {"q": q, "page": page}


@app.post("/books")
def create_book():
    data = request.get_json(silent=True) or {}   # 非 JSON 时返回 None 而不是直接 400
    if "title" not in data:
        return {"detail": "title required"}, 400  # (body, status)
    return {"title": data["title"]}, 201, {"Location": url_for("get_book", book_id=1)}


@app.get("/old")
def old():
    return redirect(url_for("search", q="flask"))  # 按端点名反解，不手写路径


@app.get("/raw")
def raw():
    resp = make_response("plain", 200)            # 需要改头时用 make_response
    resp.headers["X-Framework"] = "flask"
    resp.mimetype = "text/plain"
    return resp


if __name__ == "__main__":
    client = app.test_client()

    assert client.get("/").data == b"<h1>hello</h1>"
    assert client.get("/books/7").get_json() == {"id": 7}
    assert client.get("/books/101").status_code == 404
    assert client.get("/books/abc").status_code == 404      # int 转换失败 → 路由不匹配
    assert client.get("/search?q=x&page=oops").get_json() == {"q": "x", "page": 1}

    created = client.post("/books", json={"title": "Flask"})
    assert created.status_code == 201 and created.headers["Location"] == "/books/1"
    assert client.post("/books", data="not json").status_code == 400

    assert client.get("/old").headers["Location"] == "/search?q=flask"
    assert client.get("/raw").headers["X-Framework"] == "flask"

    with app.test_request_context():
        print("url_for:", url_for("get_book", book_id=3), url_for("search", q="py"))
    print("rules:", sorted(r.rule for r in app.url_map.iter_rules() if r.endpoint != "static"))
