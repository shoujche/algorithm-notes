"""魔术方法(dunder methods)演示。

Python 的「数据模型」协议:通过实现 __xxx__ 特殊方法,让自定义对象
支持运算符重载、内置函数(len/repr)、下标访问等语言级行为。
这就是「鸭子类型」的底层机制——协议决定能力,而非继承。
"""

from __future__ import annotations


class Vector:
    """一个二维向量,演示常见魔术方法。"""

    def __init__(self, x: float, y: float) -> None:
        # __init__:构造后初始化实例(注意:真正创建对象的是 __new__)
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        # __repr__:给开发者看的「官方」字符串,目标是可复现该对象
        # 交互式回显、repr()、容器打印元素时都会调用它
        return f"Vector({self.x!r}, {self.y!r})"

    def __eq__(self, other: object) -> bool:
        # __eq__:定义 == 的语义。默认比较 id(是否同一对象)
        if not isinstance(other, Vector):
            return NotImplemented  # 交给对方的 __eq__ 或退回身份比较
        return self.x == other.x and self.y == other.y

    def __len__(self) -> int:
        # __len__:让 len(obj) 可用。这里返回分量个数(维度)
        return 2

    def __getitem__(self, index: int) -> float:
        # __getitem__:支持下标 obj[0]、切片、以及被 for 迭代(旧式协议)
        return (self.x, self.y)[index]

    def __add__(self, other: "Vector") -> "Vector":
        # __add__:定义 + 运算符,返回新对象(向量应保持不可变语义)
        return Vector(self.x + other.x, self.y + other.y)


if __name__ == "__main__":
    a = Vector(1, 2)
    b = Vector(3, 4)

    print(repr(a))          # Vector(1, 2) —— 调用 __repr__
    print(a == Vector(1, 2))  # True —— 调用 __eq__
    print(a == b)           # False
    print(len(a))           # 2 —— 调用 __len__
    print(a[0], a[1])       # 1 2 —— 调用 __getitem__
    print(a + b)            # Vector(4, 6) —— 调用 __add__

    # 因为实现了 __getitem__,即便没写 __iter__ 也能被 for 迭代(旧式序列协议)
    for component in a:
        print("component:", component)
