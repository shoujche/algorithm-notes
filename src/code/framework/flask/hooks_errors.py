"""Flask 请求钩子的执行顺序 + 统一 JSON 错误处理。

运行：python hooks_errors.py
"""

import time

from flask import Flask, abort, g, jsonify, request
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
trace: list[str] = []


@app.before_request
def first():
    trace.append("before-1")
    g.start = time.perf_counter()


@app.before_request
def auth():
    trace.append("before-2")
    if request.path.startswith("/admin") and request.headers.get("X-Role") != "admin":
        return {"detail": "forbidden"}, 403          # 返回非 None：短路，视图不执行


@app.after_request
def add_header(response):                            # 后注册的先执行（逆序）
    trace.append("after-1")
    response.headers["X-Elapsed-Ms"] = f"{(time.perf_counter() - g.start) * 1000:.1f}"
    return response                                  # 必须返回 response


@app.after_request
def log(response):
    trace.append("after-2")
    return response


@app.teardown_request
def cleanup(exc):                                    # 无论成功失败都执行，用来释放资源
    trace.append(f"teardown({type(exc).__name__ if exc else 'ok'})")


@app.errorhandler(HTTPException)                     # 所有 4xx / 5xx HTTP 异常 → JSON
def json_error(err: HTTPException):
    return jsonify(detail=err.description), err.code


class OutOfStock(Exception):
    pass


@app.errorhandler(OutOfStock)                        # 业务异常在边界统一转 HTTP
def out_of_stock(err: OutOfStock):
    return jsonify(detail=str(err)), 409


@app.get("/ok")
def ok():
    trace.append("view")
    return {"ok": True}


@app.get("/admin")
def admin():
    trace.append("view")
    return {"secret": 1}


@app.get("/missing")
def missing():
    abort(404, description="no such book")


@app.get("/buy")
def buy():
    raise OutOfStock("sold out")


if __name__ == "__main__":
    client = app.test_client()

    assert client.get("/ok").headers["X-Elapsed-Ms"]
    assert trace == ["before-1", "before-2", "view", "after-2", "after-1", "teardown(ok)"]

    trace.clear()
    assert client.get("/admin").status_code == 403
    assert "view" not in trace                       # before_request 短路
    assert "after-1" in trace                        # 短路的响应仍会经过 after_request

    assert client.get("/missing").get_json() == {"detail": "no such book"}
    assert client.get("/nowhere").get_json()["detail"].startswith("The requested URL")
    assert client.get("/buy").get_json() == {"detail": "sold out"}
    print("order:", " → ".join(["before-1", "before-2", "view", "after-2", "after-1", "teardown"]))
