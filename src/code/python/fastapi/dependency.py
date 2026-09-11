"""依赖注入(Dependency Injection):FastAPI 的 Depends() 用法。

依赖注入让你把「获取资源 / 校验权限 / 解析公共参数」的逻辑抽成可复用函数,
路由只需声明「我需要什么」,FastAPI 负责在调用前把它准备好并注入进来。

好处:
  - 复用:get_db、get_current_user 一次定义,处处使用。
  - 解耦:路由函数专注业务,资源获取与权限校验被抽离。
  - 可测试:测试时替换依赖(app.dependency_overrides)即可 mock。
  - 可嵌套:依赖可以依赖别的依赖,FastAPI 自动按需求解整棵依赖树。
"""

from typing import Annotated

from fastapi import FastAPI, Depends, Header, HTTPException

app = FastAPI()


# ---------------------------------------------------------------------------
# 1) 最常见的依赖:获取数据库会话,用完自动关闭
# ---------------------------------------------------------------------------
def get_db():
    """yield 型依赖:yield 之前是「进入前准备」,之后是「退出后清理」。

    FastAPI 会在请求处理完毕后回来执行 yield 之后的代码,
    相当于自带 try/finally,非常适合管理需要释放的资源(连接、文件)。
    """
    db = {"conn": "fake-db-session"}  # 实际中是真正的 DB 会话
    try:
        yield db
    finally:
        # 请求结束(哪怕抛异常)都会执行:关闭连接、归还连接池。
        print("关闭数据库会话")


# ---------------------------------------------------------------------------
# 2) 嵌套依赖:get_current_user 依赖 get_db 和请求头 token
# ---------------------------------------------------------------------------
def get_current_user(
    db: Annotated[dict, Depends(get_db)],   # 依赖套依赖:先解出 db
    token: Annotated[str | None, Header()] = None,
):
    """从 token 解析当前用户;顺带演示依赖可以再依赖别的依赖。"""
    if token is None:
        raise HTTPException(status_code=401, detail="缺少 token")
    # 实际中用 token 去 db 查用户,这里简化
    return {"id": 1, "name": "alice", "db": db["conn"]}


# 只允许管理员访问的依赖,复用 get_current_user
def require_admin(
    user: Annotated[dict, Depends(get_current_user)],
):
    if user["name"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ---------------------------------------------------------------------------
# 3) 在路由里使用:声明即注入
# ---------------------------------------------------------------------------
@app.get("/me")
def read_me(user: Annotated[dict, Depends(get_current_user)]):
    # FastAPI 会:解 get_db → 解 get_current_user(读 token)→ 注入 user。
    return {"me": user["name"]}


@app.get("/admin")
def admin_panel(admin: Annotated[dict, Depends(require_admin)]):
    return {"panel": "secret", "who": admin["name"]}


# ---------------------------------------------------------------------------
# 依赖缓存(面试高频):
#   在「同一次请求」内,如果多个依赖都依赖 get_db,get_db 只会被调用一次,
#   结果被缓存复用(默认 use_cache=True)。跨请求不共享,不会缓存。
#   若想每次都重新求值,用 Depends(get_db, use_cache=False)。
# ---------------------------------------------------------------------------
