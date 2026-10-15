"""Flask 的应用上下文与请求上下文：request / session / g / current_app 为什么能当全局变量用。

运行：python contexts.py
"""

import base64
import os
import threading

from flask import Flask, current_app, g, request, session

app = Flask(__name__)
# session cookie 靠 SECRET_KEY 签名；占位值只用于本地演示，生产从环境变量注入随机值
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-not-secret")


@app.before_request
def load_user():
    g.user = request.headers.get("X-User", "anonymous")   # g：本次请求内的临时存储


@app.get("/whoami")
def whoami():
    session["visits"] = session.get("visits", 0) + 1      # session：跨请求，存在客户端 cookie
    return {"user": g.user, "visits": session["visits"], "testing": current_app.testing}


if __name__ == "__main__":
    client = app.test_client()
    assert client.get("/whoami", headers={"X-User": "ada"}).get_json()["visits"] == 1
    resp = client.get("/whoami")
    assert resp.get_json() == {"user": "anonymous", "visits": 2, "testing": False}

    # 1) session 是「签名」而不是「加密」：任何人都能解码看到内容，只是改不了
    cookie = client.get_cookie("session").value
    payload = cookie.split(".")[0]
    print("session payload:", base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))

    # 2) 出了请求上下文就不能用 request
    try:
        request.args
    except RuntimeError as e:
        print("outside request:", str(e).splitlines()[0])

    # 3) 手动推上下文：CLI、后台任务、单元测试里常用
    with app.app_context():
        assert current_app._get_current_object() is app       # 应用上下文：current_app、g
    with app.test_request_context("/whoami?q=1", headers={"X-User": "bob"}):
        assert request.args["q"] == "1"                       # 请求上下文：request、session

    # 4) 线程隔离：两个线程各自推上下文，看到的 request 互不干扰
    seen: dict[str, str] = {}

    def worker(name: str) -> None:
        with app.test_request_context(f"/?who={name}"):
            seen[name] = request.args["who"]

    threads = [threading.Thread(target=worker, args=(n,)) for n in ("t1", "t2")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert seen == {"t1": "t1", "t2": "t2"}
    print("thread isolated:", seen)
