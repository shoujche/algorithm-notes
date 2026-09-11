"""异步限流器：令牌桶（Token Bucket）实现。

面试常考「限流」——控制单位时间内的请求速率。主流算法：
  - 令牌桶 Token Bucket：以固定速率往桶里放令牌，请求取到令牌才放行。
    允许「突发流量」（桶里攒够令牌可瞬间放行一批）。
  - 漏桶 Leaky Bucket：请求以固定速率流出，强制平滑，不允许突发。

这里用 asyncio 实现一个异步令牌桶，配合 async with 使用。
"""

import asyncio
import time


class TokenBucket:
    """异步令牌桶限流器。

    参数：
        rate:     每秒补充的令牌数（即稳态 QPS）
        capacity: 桶容量（允许的最大突发量）
    """

    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity  # 初始装满
        self.updated = time.monotonic()  # monotonic 不受系统时间调整影响
        self.lock = asyncio.Lock()  # 保护 tokens 的并发读改写

    async def acquire(self, n: float = 1) -> None:
        """获取 n 个令牌，不足则异步等待（不阻塞事件循环）。"""
        while True:
            async with self.lock:
                now = time.monotonic()
                # 惰性补充：按经过的时间补令牌，上限为 capacity
                elapsed = now - self.updated
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self.updated = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                # 令牌不够，算出还差多少、需等多久
                deficit = n - self.tokens
                wait = deficit / self.rate
            await asyncio.sleep(wait)  # 注意：在锁外 sleep，避免占着锁睡觉

    async def __aenter__(self):
        await self.acquire(1)
        return self

    async def __aexit__(self, *exc):
        return False


# ============ 另一种思路：Semaphore 控制「并发数」============
# 令牌桶控制的是「速率」(QPS)，Semaphore 控制的是「同时在跑的数量」(并发度)，
# 两者常被搞混，面试可主动点破区别。
async def with_semaphore_demo():
    sem = asyncio.Semaphore(3)  # 最多 3 个协程同时进入

    async def worker(i):
        async with sem:  # 超过 3 个的会在此排队
            print(f"worker {i} running")
            await asyncio.sleep(0.1)

    await asyncio.gather(*(worker(i) for i in range(10)))


async def main():
    bucket = TokenBucket(rate=5, capacity=5)  # 5 QPS，可突发 5 个
    start = time.monotonic()

    async def call(i):
        async with bucket:  # 取不到令牌就自动等待
            print(f"请求 {i} 放行 @ {time.monotonic() - start:.2f}s")

    # 一次性发 12 个请求：前 5 个瞬发（用光初始令牌），其余按 5/s 限速
    await asyncio.gather(*(call(i) for i in range(12)))


if __name__ == "__main__":
    asyncio.run(main())
