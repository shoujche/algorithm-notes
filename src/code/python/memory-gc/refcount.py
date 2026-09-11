"""引用计数：CPython 通过 ob_refcnt 记录对象被引用次数，归零即立刻回收。"""
import sys


def show_refcount() -> None:
    obj = object()

    # 注意：getrefcount 本身会临时持有一个引用（作为函数实参），
    # 所以返回值通常比"真实引用数"多 1。
    print("初始:", sys.getrefcount(obj))  # 一般为 2（obj 变量 + 实参）

    alias = obj  # 新增一个引用 → refcount +1
    print("新增别名后:", sys.getrefcount(obj))  # 3

    holder = [obj, obj]  # 列表里放两次 → refcount +2
    print("放入列表后:", sys.getrefcount(obj))  # 5

    del alias  # 删除一个引用 → refcount -1
    print("del 别名后:", sys.getrefcount(obj))  # 4

    holder.clear()  # 列表清空 → refcount -2
    print("清空列表后:", sys.getrefcount(obj))  # 2


def auto_free() -> None:
    """引用计数归零时，__del__ 会被立即调用（确定性回收）。"""

    class Noisy:
        def __del__(self) -> None:
            print("对象被回收")

    x = Noisy()
    print("准备解除引用")
    x = None  # 唯一引用置空 → refcount 归零 → 立即回收
    print("已解除引用")


if __name__ == "__main__":
    show_refcount()
    print("-" * 20)
    auto_free()
