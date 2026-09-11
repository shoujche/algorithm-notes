"""上下文管理器(context manager)演示。

with 语句的本质:进入时调用 __enter__,离开时(无论正常或异常)调用 __exit__。
它保证「资源一定被释放」——文件关闭、锁释放、连接归还,都靠它兜底。
两种写法:实现协议的类,或用 contextlib.contextmanager 装饰生成器。
"""

import contextlib
import time


# ---------- 1. 类写法:实现 __enter__ / __exit__ ----------
class Timer:
    """计时上下文管理器:统计 with 块的执行耗时。"""

    def __enter__(self):
        # __enter__ 的返回值会赋给 as 后面的变量
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 三个参数描述块内异常(无异常时均为 None)
        self.cost = (time.perf_counter() - self.start) * 1000
        print(f"[Timer] 耗时 {self.cost:.2f}ms")
        # 返回 True 会「吞掉」异常;返回 False/None 则异常继续向上抛
        return False


# ---------- 2. 装饰器写法:contextlib.contextmanager ----------
@contextlib.contextmanager
def open_resource(name: str):
    """用生成器写上下文管理器:yield 之前是 __enter__,之后是 __exit__。"""
    print(f"[open] 打开资源 {name}")
    resource = {"name": name, "opened": True}
    try:
        yield resource  # yield 出的值即 as 变量;这里相当于 __enter__ 的返回
    finally:
        # finally 保证即使块内抛异常也会执行清理,相当于 __exit__
        resource["opened"] = False
        print(f"[close] 释放资源 {name}")


if __name__ == "__main__":
    with Timer():
        total = sum(i * i for i in range(1_000_00))
        print("计算结果:", total)

    with open_resource("db-conn") as r:
        print("使用中:", r)

    # 即便块内抛异常,finally 里的清理仍会执行
    try:
        with open_resource("file") as r:
            raise RuntimeError("模拟出错")
    except RuntimeError as e:
        print("捕获到异常,但资源已被释放:", e)
