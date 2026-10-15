"""Django 请求生命周期：中间件 → URLconf → 视图 → 中间件，单文件即可运行。

运行：python request_cycle.py
不需要 startproject：settings.configure() 在内存里给出最小配置，
用 django.test.Client 发请求，观察中间件的「洋葱」顺序。
"""

import os

import django
from django.conf import settings

settings.configure(
    DEBUG=True,
    # 密钥从环境变量读；占位值只用于本地演示，生产必须注入随机值
    SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret"),
    ALLOWED_HOSTS=["testserver"],
    ROOT_URLCONF=__name__,
    MIDDLEWARE=[
        f"{__name__}.OuterMiddleware",
        f"{__name__}.InnerMiddleware",
    ],
)
django.setup()

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import Client
from django.urls import path, reverse
from django.views import View
from django.views.decorators.http import require_http_methods

trace: list[str] = []


# ---------------------------------------------------------------------------
# 1) 中间件：__init__ 在启动时调一次，__call__ 每个请求调一次
# ---------------------------------------------------------------------------
class OuterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace.append("outer-in")
        response = self.get_response(request)   # 调用链中的下一层
        trace.append("outer-out")
        return response


class InnerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace.append("inner-in")
        response = self.get_response(request)
        trace.append("inner-out")
        response["X-Handled-By"] = "django"
        return response


# ---------------------------------------------------------------------------
# 2) 视图：函数视图 FBV 与类视图 CBV
# ---------------------------------------------------------------------------
@require_http_methods(["GET"])                   # 其他方法自动 405
def hello(request: HttpRequest) -> JsonResponse:
    trace.append("view")
    return JsonResponse({"hello": request.GET.get("name", "world")})


class BookView(View):                            # 按 HTTP 方法分发到同名方法
    def get(self, request: HttpRequest, pk: int) -> JsonResponse:
        trace.append("view")
        return JsonResponse({"id": pk})

    def delete(self, request: HttpRequest, pk: int) -> HttpResponse:
        return HttpResponse(status=204)          # 204 不能带 body


# ---------------------------------------------------------------------------
# 3) URLconf：按顺序匹配，第一个命中就停；用 name 反解 URL
# ---------------------------------------------------------------------------
urlpatterns = [
    path("hello/", hello, name="hello"),
    path("books/<int:pk>/", BookView.as_view(), name="book"),   # <int:pk> 自动转 int
]


if __name__ == "__main__":
    client = Client()

    resp = client.get(reverse("hello"), {"name": "ada"})
    assert resp.json() == {"hello": "ada"}
    assert resp["X-Handled-By"] == "django"
    # 请求方向按 MIDDLEWARE 从上到下，响应方向从下到上
    assert trace == ["outer-in", "inner-in", "view", "inner-out", "outer-out"]

    assert reverse("book", args=[7]) == "/books/7/"
    assert client.get("/books/7/").json() == {"id": 7}
    assert client.delete("/books/7/").status_code == 204
    assert client.post("/hello/").status_code == 405
    assert client.get("/books/abc/").status_code == 404     # 转换器不匹配 → 404

    print("middleware order:", " → ".join(trace[:5]))
