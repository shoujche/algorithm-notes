"""常见坑：在协程里调用阻塞函数会卡死整个事件循环。"""
import asyncio
import time


# ❌ 反例：time.sleep 是同步阻塞，期间事件循环无法调度任何协程
async def bad(name: str) -> None:
    time.sleep(1)          # 阻塞！其他协程全部被冻结
    print(f"bad {name}")


# ✅ 正解 1：换成 await 版本的异步等待
async def good(name: str) -> None:
    await asyncio.sleep(1)  # 让出控制权，事件循环可跑别的协程
    print(f"good {name}")


# ✅ 正解 2：无法避免的阻塞调用(如老库/CPU 计算)丢到线程池
def blocking_lib_call() -> int:
    time.sleep(1)
    return 42


async def offload() -> None:
    loop = asyncio.get_running_loop()
    # run_in_executor：把阻塞调用放到线程池，不冻结事件循环
    result = await loop.run_in_executor(None, blocking_lib_call)
    print("offloaded:", result)


async def main() -> None:
    # good 版本并发，约 1s 完成 3 个
    await asyncio.gather(good("1"), good("2"), good("3"))
    await offload()


if __name__ == "__main__":
    asyncio.run(main())
