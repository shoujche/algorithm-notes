"""Django REST framework：Serializer 校验、ModelViewSet、Router、权限。

运行：pip install djangorestframework && python drf_api.py
"""

import os

import django
from django.conf import settings

settings.configure(
    DEBUG=True,
    SECRET_KEY=os.environ.get("DJANGO_SECRET_KEY", "dev-only-not-secret"),
    ALLOWED_HOSTS=["testserver"],
    ROOT_URLCONF=__name__,
    INSTALLED_APPS=[
        "django.contrib.contenttypes",
        "django.contrib.auth",
        "rest_framework",
        "__main__",
    ],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    REST_FRAMEWORK={"UNAUTHENTICATED_USER": None},
)
django.setup()

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection, models
from django.urls import include, path
from rest_framework import permissions, serializers, viewsets
from rest_framework.routers import DefaultRouter
from rest_framework.test import APIClient


class Author(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        app_label = "__main__"


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        app_label = "__main__"
        ordering = ["id"]


# ---------------------------------------------------------------------------
# Serializer = 入参校验 + 出参序列化（≈ Pydantic BaseModel）
# ---------------------------------------------------------------------------
class BookSerializer(serializers.ModelSerializer):
    # 外键用作者名读写，而不是暴露数字 id
    author = serializers.SlugRelatedField(slug_field="name", queryset=Author.objects.all())

    class Meta:
        model = Book
        fields = ["id", "title", "author", "price"]

    def validate_price(self, value):           # 单字段校验 ≈ Pydantic @field_validator
        if value <= 0:
            raise serializers.ValidationError("price must be positive")
        return value

    def validate(self, attrs):                 # 跨字段校验 ≈ Pydantic @model_validator
        # PATCH 只带部分字段，缺的从已有实例补齐
        title = attrs.get("title", getattr(self.instance, "title", ""))
        author = attrs.get("author", getattr(self.instance, "author", None))
        if author and title.lower() == author.name.lower():
            raise serializers.ValidationError("title must differ from author")
        return attrs


# ---------------------------------------------------------------------------
# ModelViewSet：list / create / retrieve / update / partial_update / destroy
# ---------------------------------------------------------------------------
class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("author")       # 序列化 author 时不 N+1
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


router = DefaultRouter()
router.register("books", BookViewSet)
urlpatterns = [path("api/", include(router.urls))]


if __name__ == "__main__":
    call_command("migrate", run_syncdb=True, verbosity=0)   # auth 等内置表
    with connection.schema_editor() as editor:
        editor.create_model(Author)
        editor.create_model(Book)
    Author.objects.create(name="Ada")

    api = APIClient()
    assert api.get("/api/books/").json() == []
    # 匿名用户只读：写操作 403
    assert api.post("/api/books/", {"title": "X", "author": "Ada", "price": "1"}).status_code == 403

    api.force_authenticate(User.objects.create_user("u", password="pw-for-demo-only"))
    bad = api.post("/api/books/", {"title": "X", "author": "Nobody", "price": "0"})
    assert bad.status_code == 400
    assert set(bad.json()) == {"author", "price"}            # 一次返回所有字段错误

    ok = api.post("/api/books/", {"title": "DRF", "author": "Ada", "price": "9.50"})
    assert ok.status_code == 201
    assert ok.json() == {"id": 1, "title": "DRF", "author": "Ada", "price": "9.50"}
    assert api.patch("/api/books/1/", {"price": "12.00"}).json()["price"] == "12.00"
    assert api.delete("/api/books/1/").status_code == 204

    print("router names:", sorted({p.name for p in router.urls if p.name}))
