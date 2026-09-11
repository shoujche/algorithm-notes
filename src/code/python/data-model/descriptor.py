"""描述符(descriptor)与 property 演示。

描述符是「实现了 __get__/__set__/__delete__ 的类」,当它作为另一个类的
类属性时,对该属性的读写会被这些方法接管。它是 property、classmethod、
staticmethod、以及 ORM 字段的底层机制。

property 本质就是一个「数据描述符」——它把 getter/setter 封装成描述符。
"""

from __future__ import annotations


# ---------- 1. 自定义描述符:带校验的属性 ----------
class Positive:
    """要求被赋值必须为正数的描述符(数据描述符:同时有 __get__/__set__)。"""

    def __set_name__(self, owner, name):
        # Python 会自动传入该描述符在宿主类中的属性名
        self.private_name = f"_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self  # 通过类访问(Class.attr)时返回描述符本身
        return getattr(obj, self.private_name)

    def __set__(self, obj, value):
        # 拦截赋值:在这里做校验,把真实值存到实例的私有属性
        if value <= 0:
            raise ValueError(f"{self.private_name} 必须为正数,收到 {value}")
        setattr(obj, self.private_name, value)


class Account:
    balance = Positive()  # 类属性即描述符实例,被所有实例共享逻辑

    def __init__(self, balance: float) -> None:
        self.balance = balance  # 触发 Positive.__set__ 做校验


# ---------- 2. property 本质是描述符 ----------
class Circle:
    def __init__(self, radius: float) -> None:
        self._radius = radius

    @property
    def radius(self) -> float:
        # @property 把 radius 变成一个数据描述符,读属性时调用此 getter
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        # 写属性时调用此 setter,可在此加校验
        if value <= 0:
            raise ValueError("半径必须为正数")
        self._radius = value

    @property
    def area(self) -> float:
        # 只读计算属性:没有 setter,像访问字段一样访问 obj.area
        return 3.14159 * self._radius ** 2


if __name__ == "__main__":
    acc = Account(100)
    print("余额:", acc.balance)  # 触发 __get__
    try:
        acc.balance = -50       # 触发 __set__,校验失败
    except ValueError as e:
        print("赋值被拒:", e)

    c = Circle(2)
    print("半径:", c.radius, "面积:", c.area)
    c.radius = 5                # 触发 property 的 setter
    print("新面积:", c.area)

    # 证明 property 确实是描述符:它定义在类上且有 __get__
    print("radius 是描述符吗:", hasattr(type(c).__dict__["radius"], "__get__"))
