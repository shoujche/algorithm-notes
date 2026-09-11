"""手写三大经典装饰器：计时 timer、重试 retry、缓存 cache。

面试要点：
1. 装饰器本质是「接收函数、返回函数」的高阶函数。
2. 必须用 functools.wraps 保留原函数的 __name__ / __doc__ / 签名，
   否则被装饰后函数「改名换姓」，日志、调试、文档都会出错。
3. 带参数的装饰器 = 三层嵌套：参数层 -> 装饰层 -> 包裹层。
"""

import functools
import time


# ============ 1. 计时装饰器：无参数 ============
def timer(func):
    """统计函数执行耗时（wall-clock time）。"""

    @functools.wraps(func)  # 保留原函数元信息，关键！
    def wrapper(*args, **kwargs):
        start = time.perf_counter()  # perf_counter 精度高，专用于测耗时
        try:
            return func(*args, **kwargs)
        finally:
            # 放 finally：即使函数抛异常也能打印耗时
            cost = (time.perf_counter() - start) * 1000
            print(f"[timer] {func.__name__} 耗时 {cost:.2f} ms")

    return wrapper


# ============ 2. 重试装饰器：带参数（次数 + 延迟 + 异常类型）============
def retry(times=3, delay=0.5, exceptions=(Exception,)):
    """失败自动重试。

    参数：
        times:      最大尝试次数（含首次）
        delay:      每次重试前的等待秒数
        exceptions: 只捕获这些异常类型，其余异常直接抛出
    """

    def decorator(func):  # 第二层：真正的装饰器
        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # 第三层：调用时的包裹逻辑
            last_exc = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    print(f"[retry] {func.__name__} 第 {attempt}/{times} 次失败：{exc}")
                    if attempt < times:
                        time.sleep(delay)
            # 重试全部耗尽，抛出最后一次异常（保留原始堆栈）
            raise last_exc

        return wrapper

    return decorator


# ============ 3. 缓存装饰器：手写 memoize ============
def cache(func):
    """把入参映射到返回值，相同入参不重复计算（等价简化版 lru_cache）。"""

    store = {}  # 闭包持有的缓存字典

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 用 args + 排序后的 kwargs 构造可哈希的 key
        key = (args, tuple(sorted(kwargs.items())))
        if key not in store:
            store[key] = func(*args, **kwargs)
        return store[key]

    wrapper.cache_clear = store.clear  # 暴露清空缓存的能力，模仿标准库
    return wrapper


# ============ 演示 ============
@timer
@retry(times=3, delay=0.2, exceptions=(ValueError,))
def flaky(n):
    """有 60% 概率失败的函数，用来演示重试。"""
    import random

    if random.random() < 0.6:
        raise ValueError("模拟随机失败")
    return n * n


@cache
def fib(n):
    """朴素递归斐波那契，加了 cache 后从指数级降到线性。"""
    return n if n < 2 else fib(n - 1) + fib(n - 2)


if __name__ == "__main__":
    print("fib(30) =", fib(30))  # 秒出结果，因为有缓存
    try:
        print("flaky =", flaky(5))
    except ValueError:
        print("重试耗尽仍失败")
