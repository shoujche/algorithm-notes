"""循环引用：两个对象互相引用，引用计数永不归零，只能靠 gc 的标记-清除回收。"""
import gc


class Node:
    def __init__(self, name: str) -> None:
        self.name = name
        self.partner: "Node | None" = None

    def __del__(self) -> None:
        print(f"回收 {self.name}")


def make_cycle() -> None:
    a = Node("A")
    b = Node("B")
    a.partner = b  # A → B
    b.partner = a  # B → A，形成循环引用
    # 函数返回后，局部变量 a、b 消失，但 A、B 仍互相引用，
    # 引用计数都停在 1，无法归零 → 引用计数机制无法回收。


def demo() -> None:
    # 先关闭自动 gc，观察循环引用不会被引用计数回收
    gc.disable()
    make_cycle()
    print("函数已返回，若只靠引用计数，A/B 不会被回收")

    # 手动触发标记-清除，回收不可达的循环引用对象
    print("执行 gc.collect() ...")
    collected = gc.collect()  # 返回本次回收的对象数
    print(f"gc 回收了 {collected} 个对象")

    gc.enable()


if __name__ == "__main__":
    demo()
