"""应用工厂 + 蓝图 + 扩展的 init_app 模式：Flask 中大型项目的标准骨架。

运行：python factory_blueprint.py
真实项目里这些会拆成 config.py / extensions.py / books.py / __init__.py 多个文件。
"""

import os

from flask import Blueprint, Flask, current_app


# ---------------------------------------------------------------------------
# config.py：配置类，敏感值从环境变量读
# ---------------------------------------------------------------------------
class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-not-secret")
    PAGE_SIZE = 20


class TestConfig(Config):
    TESTING = True
    PAGE_SIZE = 2


# ---------------------------------------------------------------------------
# extensions.py：扩展先创建、不绑定 app，工厂里再 init_app（避免循环导入）
# ---------------------------------------------------------------------------
class Cache:
    """仿照 Flask-SQLAlchemy / Flask-Caching 的扩展写法。"""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}

    def init_app(self, app: Flask) -> None:
        app.extensions["cache"] = self               # 惯例：挂在 app.extensions 上


cache = Cache()


# ---------------------------------------------------------------------------
# books.py：蓝图 = 一组路由 / 钩子的可注册模块
# ---------------------------------------------------------------------------
bp = Blueprint("books", __name__)


@bp.get("/")
def list_books():
    size = current_app.config["PAGE_SIZE"]           # 通过 current_app 读当前 app 的配置
    return {"page_size": size, "testing": current_app.testing}


@bp.before_request
def only_for_books():                                # 蓝图级钩子：只对本蓝图路由生效
    cache.store["hits"] = cache.store.get("hits", 0) + 1


# ---------------------------------------------------------------------------
# __init__.py：应用工厂
# ---------------------------------------------------------------------------
def create_app(config: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.from_prefixed_env()                   # FLASK_PAGE_SIZE=50 → PAGE_SIZE=50（按 JSON 解析）

    cache.init_app(app)
    app.register_blueprint(bp, url_prefix="/books")
    app.register_blueprint(bp, url_prefix="/v2/books", name="books_v2")   # 同一蓝图可注册多次

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


if __name__ == "__main__":
    prod, test = create_app(), create_app(TestConfig)     # 两个互相隔离的实例
    assert prod.test_client().get("/books/").get_json() == {"page_size": 20, "testing": False}
    assert test.test_client().get("/books/").get_json() == {"page_size": 2, "testing": True}
    assert test.test_client().get("/v2/books/").status_code == 200

    test.test_client().get("/health")                   # 不经过蓝图钩子
    assert cache.store["hits"] == 3

    os.environ["FLASK_PAGE_SIZE"] = "50"
    assert create_app().config["PAGE_SIZE"] == 50       # 环境变量覆盖，且已转成 int

    with test.test_request_context():
        from flask import url_for
        print("endpoints:", url_for("books.list_books"), url_for("books_v2.list_books"))
