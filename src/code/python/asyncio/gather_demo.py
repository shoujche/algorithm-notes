"""协程并发：gather 让多个 await 同时推进，总耗时≈最慢的一个而非之和。"""
import asyncio
import time


async def fetch(name: str, delay: float) -> str:
    print(f"  开始 {name}")
    await asyncio.sleep(delay)  # 挂起，事件循环切去跑别的协程
    print(f"  完成 {name}")
    return f"{name} 用时 {delay}s"


async def sequential() -> None:
    # 逐个 await：串行，总时间 = 之和
    start = time.perf_counter()
    await fetch("A", 1)
    await fetch("B", 2)
    print(f"sequential: {time.perf_counter() - start:.1f}s")  # ~3s


async def concurrent() -> None:
    # gather：并发，总时间 = max
    start = time.perf_counter()
    results = await asyncio.gather(fetch("A", 1), fetch("B", 2))
    print(results)
    print(f"concurrent: {time.perf_counter() - start:.1f}s")  # ~2s


async def main() -> None:
    await sequential()
    await concurrent()


if __name__ == "__main__":
    asyncio.run(main())  # 创建事件循环、运行 main、收尾关闭
