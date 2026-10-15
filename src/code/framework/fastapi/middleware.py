"""中间件(Middleware)与生命周期(lifespan)。

中间件:包在每个请求外面的一层「洋葱皮」,请求进来先经过它、响应出去再经过它。
       适合做:记录耗时、统一日志、加公共响应头、限流、鉴权前置。

lifespan:管理应用「启动 / 关闭」时的资源。
       启动时:建连接池、加载模型、预热缓存。
       关闭时:优雅释放这些资源。取代了旧的 @app.on_event("startup"/"shutdown")。
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request


# ---------------------------------------------------------------------------
# 1) lifespan:应用级资源的启动与关闭
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- 启动阶段:yield 之前的代码在应用启动时执行一次 ----
    print("应用启动:初始化数据库连接池 / 加载模型")
    app.state.db_pool = {"pool": "fake-pool"}  # 挂到 app.state 供全局使用
    app.state.model = {"weights": "loaded"}

    yield  # ← 应用在这里正常运行,处理所有请求

    # ---- 关闭阶段:yield 之后的代码在应用退出时执行一次 ----
    print("应用关闭:释放连接池 / 卸载模型")
    app.state.db_pool = None


# 把 lifespan 传给 app,FastAPI 会在启动/关闭时驱动它
app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# 2) 中间件:记录每个请求的处理耗时
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    """洋葱模型:call_next 之前是「请求前」,之后是「响应后」。"""
    start = time.perf_counter()

    # call_next 把请求继续往内传(经过后续中间件与真正的路由),拿到响应。
    response = await call_next(request)

    # 响应出去前,算出耗时并塞进响应头,便于观测与排查慢接口。
    elapsed = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
    print(f"{request.method} {request.url.path} 耗时 {elapsed*1000:.1f}ms")
    return response


# ---------------------------------------------------------------------------
# 3) 路由里通过 request.app.state 使用 lifespan 建好的资源
# ---------------------------------------------------------------------------
@app.get("/ping")
async def ping(request: Request):
    pool = request.app.state.db_pool
    return {"pong": True, "pool": pool}


# ---------------------------------------------------------------------------
# 执行顺序(单个请求):
#   中间件(前)→ 依赖 → 路由函数 → 依赖清理 → 中间件(后)
# 多个中间件按注册相反顺序层层包裹,像洋葱一样进去再出来。
#
# 面试点:为什么用 lifespan 而不是每次请求都建连接?
#   —— 连接池 / 模型加载昂贵,应在启动时建一次、全程复用,
#      关闭时统一释放,避免每请求的重复开销与资源泄漏。
# ---------------------------------------------------------------------------
