"""装饰器(decorator)演示。

装饰器本质:一个「接收函数、返回函数」的高阶函数,用 @ 语法糖
把 func = decorator(func) 写得更优雅。它让我们在不改动原函数代码的前提下
增强其行为(日志、计时、缓存、权限校验……)。
"""

import functools
import time


# ---------- 1. 基础装饰器 ----------
def timer(func):
    """打印函数执行耗时的最简装饰器。"""

    @functools.wraps(func)  # 关键:保留原函数的 __name__/__doc__ 等元信息
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)  # 调用被装饰的原函数
        cost = (time.perf_counter() - start) * 1000
        print(f"[timer] {func.__name__} 耗时 {cost:.2f}ms")
        return result

    return wrapper


# ---------- 2. 带参数的装饰器(三层嵌套) ----------
def retry(times: int):
    """失败重试装饰器。外层接收参数,返回真正的装饰器。"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 演示用
                    last_exc = exc
                    print(f"[retry] 第 {i + 1} 次失败: {exc}")
            raise last_exc  # 重试次数用尽,抛出最后一次异常

        return wrapper

    return decorator


# ---------- 3. 类装饰器(用实例可调用实现) ----------
class CountCalls:
    """统计函数被调用的次数。__call__ 让实例可像函数一样调用。"""

    def __init__(self, func):
        functools.update_wrapper(self, func)  # 等价于 wraps 的手动版
        self.func = func
        self.count = 0

    def __call__(self, *args, **kwargs):
        self.count += 1
        print(f"[count] {self.func.__name__} 第 {self.count} 次调用")
        return self.func(*args, **kwargs)


@timer
@retry(times=3)
def flaky_add(a: int, b: int) -> int:
    """一个偶尔失败的加法(演示重试)。"""
    if time.time_ns() % 3 == 0:
        raise ValueError("随机失败")
    return a + b


@CountCalls
def greet(name: str) -> str:
    return f"Hello, {name}"


if __name__ == "__main__":
    print(flaky_add(1, 2))
    # 因为用了 functools.wraps,元信息未被 wrapper 覆盖
    print("函数名仍是:", flaky_add.__name__)

    greet("Alice")
    greet("Bob")
    print("greet 被调用次数:", greet.count)
