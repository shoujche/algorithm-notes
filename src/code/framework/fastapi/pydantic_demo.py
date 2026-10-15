"""Pydantic 模型:FastAPI 请求体的自动校验与类型转换。

Pydantic 是 FastAPI 的核心依赖之一。你用 BaseModel 声明「数据长什么样」,
FastAPI 就会在请求进来时自动:
  1. 解析 JSON body;
  2. 校验字段类型与约束(不合法直接返回 422,轮不到你的业务代码);
  3. 做类型转换(如字符串 "18" → int 18);
  4. 生成 OpenAPI 文档(/docs 里的交互式表单)。
"""

from datetime import datetime
from enum import Enum

from fastapi import FastAPI
from pydantic import BaseModel, Field, EmailStr, field_validator

app = FastAPI()


class Role(str, Enum):
    """枚举类型:请求里只能传这三个值之一,否则 422。"""
    admin = "admin"
    user = "user"
    guest = "guest"


class UserCreate(BaseModel):
    """创建用户的请求体模型。

    Field(...) 里的 ... 表示必填;给默认值则表示可选。
    Field 还能加各种约束(长度、大小、正则),校验不过自动 422。
    """

    # 必填,长度 3~20
    username: str = Field(..., min_length=3, max_length=20, description="用户名")
    # 邮箱格式校验(需要 pydantic[email])
    email: EmailStr
    # 数值范围约束:0 < age <= 150
    age: int = Field(..., gt=0, le=150)
    # 可选字段,默认 user
    role: Role = Field(default=Role.user)
    # 带默认工厂:未传时用当前时间
    created_at: datetime = Field(default_factory=datetime.now)
    # 列表字段,可选,默认空列表(用 default_factory 避免可变默认值坑)
    tags: list[str] = Field(default_factory=list)

    @field_validator("username")
    @classmethod
    def username_no_space(cls, v: str) -> str:
        """自定义校验器:用户名不允许含空格。"""
        if " " in v:
            raise ValueError("用户名不能包含空格")
        return v


class UserOut(BaseModel):
    """响应模型:用 response_model 控制返回字段,避免泄露敏感数据(如密码)。"""
    username: str
    email: EmailStr
    role: Role


@app.post("/users", response_model=UserOut)
def create_user(user: UserCreate):
    # 能进到这里,说明 user 已经通过全部校验并完成类型转换。
    # 直接当作合法的强类型对象使用,业务代码无需再写一行校验。
    print(f"创建用户:{user.username},注册于 {user.created_at}")
    # 返回 dict 或模型都可以;response_model 会过滤成只含 UserOut 的字段。
    return user


# ---------------------------------------------------------------------------
# 类型转换示例:客户端传 {"age": "18"} 也能被转成 int 18;
# 但传 {"age": "abc"} 会直接 422,错误信息里会精确指出哪个字段、为什么。
#
# 面试点:校验发生在业务逻辑之前 —— 这是「让非法数据进不了系统」的
# 「解析而非校验(parse, don't validate)」思想的工程落地。
# ---------------------------------------------------------------------------
