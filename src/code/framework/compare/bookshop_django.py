"""同一个书店接口 · Django 版：创建（校验）/ 查询（404）/ 购买（409 防超卖）。

运行：python bookshop_django.py
"""

import json
import os

import django
from django.conf import settings

settings.configure(
    SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret"),
    ALLOWED_HOSTS=["testserver"],
    ROOT_URLCONF=__name__,
    INSTALLED_APPS=["__main__"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
django.setup()

from django import forms
from django.db import connection, models
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.test import Client
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


class Book(models.Model):                        # ORM：内置，Active Record 风格
    title = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    stock = models.PositiveIntegerField(default=0, blank=True)   # blank=True：表单里可省略

    class Meta:
        app_label = "__main__"


class BookForm(forms.ModelForm):                 # 校验：Form / ModelForm（API 项目用 DRF）
    class Meta:
        model = Book
        fields = ["title", "price", "stock"]

    def clean_price(self):
        if self.cleaned_data["price"] <= 0:
            raise forms.ValidationError("must be > 0")
        return self.cleaned_data["price"]


def to_dict(b: Book) -> dict:
    return {"id": b.id, "title": b.title, "price": str(b.price), "stock": b.stock}


@csrf_exempt                                     # 纯 JSON API 演示；表单场景保留 CSRF
@require_POST
def create_book(request):
    form = BookForm(json.loads(request.body))    # request 是视图的第一个参数（显式）
    if not form.is_valid():
        return JsonResponse({"detail": form.errors}, status=400)
    return JsonResponse(to_dict(form.save()), status=201)


def get_book(request, pk: int):
    return JsonResponse(to_dict(get_object_or_404(Book, pk=pk)))


@csrf_exempt
@require_POST
def buy(request, pk: int):
    updated = Book.objects.filter(pk=pk, stock__gt=0).update(stock=F("stock") - 1)
    if not updated:
        return JsonResponse({"detail": "sold out"}, status=409)
    return JsonResponse({"ok": True})


urlpatterns = [                                  # 路由：集中写在 urls.py
    path("books/", create_book),
    path("books/<int:pk>/", get_book),
    path("books/<int:pk>/buy/", buy),
]


if __name__ == "__main__":
    with connection.schema_editor() as editor:
        editor.create_model(Book)
    c = Client()
    post = lambda url, body=None: c.post(url, json.dumps(body or {}), content_type="application/json")

    assert post("/books/", {"title": "Django", "price": "30", "stock": 1}).status_code == 201
    bad = post("/books/", {"title": "", "price": "0"})
    assert bad.status_code == 400 and set(bad.json()["detail"]) == {"title", "price"}
    assert c.get("/books/1/").json()["price"] == "30.00"
    assert c.get("/books/99/").status_code == 404
    assert [post("/books/1/buy/").status_code for _ in range(2)] == [200, 409]
    print("django: 201 / 400 / 404 / 200 → 409")
