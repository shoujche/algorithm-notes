"""Flask 测试工具 + async 视图的真相：能在请求内部并发，但不提高 worker 吞吐。

运行：pip install "flask[async]" && python testing_async.py
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen

import click
from flask import Flask
from werkzeug.serving import make_server


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing

    @app.get("/fanout")
    async def fanout():
        # async 视图的正确用途：在「一个请求内部」并发调用多个下游
        async def call(name: str) -> str:
            await asyncio.sleep(0.2)                 # 假装请求下游服务
            return name

        return {"results": await asyncio.gather(call("a"), call("b"), call("c"))}

    @app.cli.command("seed")
    @click.option("--count", default=3)
    def seed(count: int):
        """自定义命令：flask --app testing_async seed --count 5"""
        click.echo(f"seeded {count}")

    return app


def burst(app: Flask, threaded: bool, n: int = 3) -> float:
    """起一个真实 WSGI 服务器，n 个客户端同时请求 /fanout，返回总耗时。"""
    server = make_server("127.0.0.1", 0, app, threaded=threaded)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/fanout"
    start = time.perf_counter()
    with ThreadPoolExecutor(n) as pool:
        list(pool.map(lambda _: urlopen(url).read(), range(n)))
    elapsed = time.perf_counter() - start
    server.shutdown()
    return elapsed


if __name__ == "__main__":
    logging.getLogger("werkzeug").setLevel(logging.ERROR)   # 关掉访问日志
    app = create_app(testing=True)

    # 1) 测试客户端：不起服务器，直接调用 WSGI 应用
    client = app.test_client()
    start = time.perf_counter()
    assert client.get("/fanout").get_json() == {"results": ["a", "b", "c"]}
    one = time.perf_counter() - start
    assert one < 0.5                                 # 请求内部 3 个下游并发：≈0.2s 而不是 0.6s

    # 2) CLI 测试
    result = app.test_cli_runner().invoke(args=["seed", "--count", "5"])
    assert result.output.strip() == "seeded 5"

    # 3) 单线程 worker：async 视图跑完自己的事件循环才返回，
    #    worker 不能趁它 await 时去接别的请求 → 3 个并发请求排队
    single = burst(app, threaded=False)
    # 多线程 worker：并发能力来自线程数，而不是 async
    multi = burst(app, threaded=True)
    assert single > 0.55 and multi < 0.45

    print(f"one request={one:.2f}s  3 concurrent: single-thread={single:.2f}s "
          f"threaded={multi:.2f}s")
