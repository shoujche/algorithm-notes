"""异步并发池：限制最大并发数跑一批协程任务。

场景：手上有 100 个 URL 要抓，但不能一次性发 100 个请求（打爆对端 / 本地资源）。
经典解法：asyncio.Semaphore 限制「同时在跑」的数量，再用 gather 收集全部结果。

要点：
1. Semaphore(N) = 最多 N 个协程能同时进入临界区，其余排队。
2. 用 async with sem 包住真正的任务体，让「获取信号量」自动配对「释放」。
3. gather 保持结果顺序 = 传入协程的顺序，与完成先后无关。
"""

import asyncio


async def gather_with_concurrency(limit: int, *coros):
    """并发运行一批协程，但同时在跑的不超过 limit 个。

    参数：
        limit: 最大并发数
        coros: 待运行的协程对象们
    返回：与传入顺序一致的结果列表。
    """
    sem = asyncio.Semaphore(limit)

    async def _wrap(coro):
        async with sem:  # 超出 limit 的协程在此挂起等待
            return await coro

    # 每个协程都套上信号量再交给 gather
    return await asyncio.gather(*(_wrap(c) for c in coros))


# ============ 演示：模拟 10 个耗时任务，并发上限 3 ============
async def fetch(i: int) -> int:
    """模拟一个 I/O 任务（比如 HTTP 请求）。"""
    print(f"  → 开始任务 {i}")
    await asyncio.sleep(0.3)  # 假装在等网络
    print(f"  ✓ 完成任务 {i}")
    return i * i


async def main():
    tasks = [fetch(i) for i in range(10)]
    # 10 个任务，但任意时刻最多 3 个在跑，总耗时约 ceil(10/3)*0.3 ≈ 1.2s
    results = await gather_with_concurrency(3, *tasks)
    print("结果（顺序不变）:", results)


# ============ 进阶：用 TaskGroup（Python 3.11+，结构化并发）============
async def main_taskgroup():
    """3.11+ 推荐用 asyncio.TaskGroup：任一子任务异常会自动取消其余任务。"""
    sem = asyncio.Semaphore(3)

    async def run(i):
        async with sem:
            await asyncio.sleep(0.3)
            return i * i

    async with asyncio.TaskGroup() as tg:
        handles = [tg.create_task(run(i)) for i in range(10)]
    return [h.result() for h in handles]


if __name__ == "__main__":
    asyncio.run(main())
