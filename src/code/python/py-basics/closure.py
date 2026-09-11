"""闭包与延迟绑定陷阱(late binding closure)。

坑:闭包捕获的是"变量"本身,不是创建闭包时该变量的值。
循环里创建的多个函数,都引用同一个循环变量 i;等到真正调用时,
i 早已是循环结束后的最终值,于是所有函数返回同一个结果。
"""


def make_multipliers_bug():
    """错误示范:三个函数都引用同一个 i,最终 i=2。"""
    funcs = []
    for i in range(3):
        funcs.append(lambda x: x * i)  # 捕获变量 i,而非当前值
    return funcs


def make_multipliers_fix_default():
    """修复一:用默认参数在定义时"快照"当前 i 的值。"""
    funcs = []
    for i in range(3):
        funcs.append(lambda x, i=i: x * i)  # i=i 在定义时求值,绑定当前值
    return funcs


def make_multipliers_fix_factory():
    """修复二:用工厂函数,每次调用产生独立作用域。"""
    def multiplier(i):
        return lambda x: x * i
    return [multiplier(i) for i in range(3)]


if __name__ == "__main__":
    print("=== 有坑版本(延迟绑定)===")
    for f in make_multipliers_bug():
        print(f(10), end=" ")  # 期望 0 10 20,实际 20 20 20
    print("  <- 全是 20,因为循环结束时 i=2")

    print("\n=== 修复一:默认参数快照 ===")
    for f in make_multipliers_fix_default():
        print(f(10), end=" ")  # 0 10 20
    print()

    print("\n=== 修复二:工厂函数 ===")
    for f in make_multipliers_fix_factory():
        print(f(10), end=" ")  # 0 10 20
    print()
