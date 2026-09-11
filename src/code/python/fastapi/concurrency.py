"""FastAPI 并发模型:async def 路由 vs 普通 def 路由。

核心结论:
  - `async def` 路由 —— 直接跑在事件循环(event loop)所在的主线程上。
  - 普通 `def` 路由 —— FastAPI(Starlette)会把它丢到线程池(threadpool)执行,
    避免同步阻塞代码卡住事件循环。

所以「用哪种写法」取决于你的函数内部是同步阻塞还是异步非阻塞:
  - 全链路 async(有 await 的异步库)→ 用 async def。
  - 内部是同步阻塞调用(老库、无异步版本)→ 用普通 def,交给线程池。
"""

import asyncio
import time

import httpx
from fastapi import FastAPI

app = FastAPI()


# ---------------------------------------------------------------------------
# 1) async def 路由:跑在事件循环上,内部必须全程 await 非阻塞
# ---------------------------------------------------------------------------
@app.get("/async-good")
async def async_good():
    # httpx.AsyncClient 是异步 HTTP 库,await 期间事件循环可去处理别的请求。
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://httpbin.org/delay/1")
    # 高并发下这类写法能用单线程扛住成千上万个「在等待」的请求。
    return {"status": resp.status_code}


# ---------------------------------------------------------------------------
# 2) async def 路由里的阻塞陷阱 —— 反面教材,千万别这么写
# ---------------------------------------------------------------------------
@app.get("/async-bad")
async def async_bad():
    # time.sleep 是同步阻塞调用:它不会把控制权还给事件循环。
    # 结果是整个事件循环被卡死 3 秒,期间所有其他并发请求全部冻结!
    time.sleep(3)  # ❌ 阻塞事件循环
    return {"msg": "我卡住了所有人"}


# 正确做法:async 路由里遇到无法避免的阻塞调用,丢到线程池
@app.get("/async-fixed")
async def async_fixed():
    loop = asyncio.get_running_loop()
    # run_in_executor(None, ...) 用默认线程池执行阻塞函数,不占用事件循环。
    await loop.run_in_executor(None, time.sleep, 3)
    return {"msg": "阻塞调用被移到线程池,循环没被卡"}


# ---------------------------------------------------------------------------
# 3) 普通 def 路由:FastAPI 自动丢到线程池,同步阻塞代码是安全的
# ---------------------------------------------------------------------------
@app.get("/sync-ok")
def sync_ok():
    # 这里可以放心写同步阻塞代码(老的数据库驱动、requests、CPU 小计算)。
    # 因为 FastAPI 检测到这是普通 def,会在独立线程里运行它,
    # 事件循环所在的主线程不受影响。
    time.sleep(3)  # ✅ 在线程池里睡,不卡事件循环
    return {"msg": "普通 def 被丢到线程池,安全"}


# ---------------------------------------------------------------------------
# 决策速查表
# ---------------------------------------------------------------------------
#   内部调用类型          推荐路由写法        原因
#   ------------------    ----------------    ------------------------------
#   异步库(有 await)     async def           跑在事件循环,最高并发
#   同步阻塞(无异步版)   普通 def            FastAPI 自动丢线程池,不卡循环
#   async 里混了阻塞      async def + executor 手动 run_in_executor 兜底
#
# 反模式:async def 路由里直接写同步阻塞代码 —— 单个慢请求拖垮全部并发。
