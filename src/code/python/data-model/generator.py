"""迭代器与生成器(iterator & generator)演示。

- 可迭代对象(Iterable):实现 __iter__,能被 for 遍历。
- 迭代器(Iterator):实现 __iter__ + __next__,记录遍历位置,用 next() 取值。
- 生成器(Generator):用 yield 写的函数,是「自动实现了迭代器协议」的语法糖。
生成器最大的价值是「惰性求值 / 省内存」——用多少算多少,不一次性物化。
"""

import sys


# ---------- 1. 手写迭代器:实现 __iter__ / __next__ ----------
class Countdown:
    """从 n 倒数到 1 的迭代器。"""

    def __init__(self, n: int) -> None:
        self.current = n

    def __iter__(self):
        # 迭代器自身也是可迭代的,返回 self 即可(for 会先调用它)
        return self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration  # 用 StopIteration 通知「取完了」
        value = self.current
        self.current -= 1
        return value


# ---------- 2. 生成器:用 yield 实现同样的倒数 ----------
def countdown_gen(n: int):
    """等价于上面的 Countdown,但代码极简。

    函数体内出现 yield,调用它不会立即执行,而是返回一个生成器对象;
    每次 next() 执行到 yield 处「暂停」并交出值,下次从暂停点继续。
    """
    while n > 0:
        yield n
        n -= 1


# ---------- 3. 生成器省内存:惰性 vs 一次性物化 ----------
def first_n_squares_list(n: int) -> list[int]:
    """列表:一次性把所有结果放进内存。"""
    return [i * i for i in range(n)]


def first_n_squares_gen(n: int):
    """生成器:一次只产出一个,内存占用恒定。"""
    for i in range(n):
        yield i * i


if __name__ == "__main__":
    print(list(Countdown(3)))       # [3, 2, 1]
    print(list(countdown_gen(3)))   # [3, 2, 1]

    # 对比内存:列表把 100000 个数全存下;生成器只是个「配方」
    big_list = first_n_squares_list(100_000)
    big_gen = first_n_squares_gen(100_000)
    print("list 占用字节:", sys.getsizeof(big_list))  # 很大
    print("gen  占用字节:", sys.getsizeof(big_gen))   # 极小且恒定

    # yield from:把子可迭代对象的值「透传」出去,常用于组合生成器
    def chain(*iterables):
        for it in iterables:
            yield from it  # 等价于 for x in it: yield x

    print(list(chain([1, 2], (3, 4), countdown_gen(2))))  # [1, 2, 3, 4, 2, 1]
