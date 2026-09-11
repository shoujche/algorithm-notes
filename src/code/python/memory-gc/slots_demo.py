"""__slots__：用元组固定属性名，省去每实例的 __dict__，降低内存并禁止动态属性。"""
import sys


class Point:
    """普通类：每个实例带一个 __dict__，可任意添加属性，但更占内存。"""

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class SlotPoint:
    """带 __slots__：属性存在固定槽位，无 __dict__，内存更省。"""

    __slots__ = ("x", "y")  # 只允许 x、y 两个属性

    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def compare_memory() -> None:
    p = Point(1, 2)
    s = SlotPoint(1, 2)

    # 普通实例有 __dict__，额外占用内存
    print("Point 有 __dict__:", p.__dict__)
    print("Point 实例大小 :", sys.getsizeof(p), "+ dict", sys.getsizeof(p.__dict__))
    print("SlotPoint 实例大小:", sys.getsizeof(s))  # 通常明显更小

    # 动态属性：普通类允许，__slots__ 类禁止
    p.z = 3  # OK
    print("Point 动态属性 z:", p.z)
    try:
        s.z = 3  # 抛 AttributeError
    except AttributeError as e:
        print("SlotPoint 禁止动态属性:", e)


if __name__ == "__main__":
    compare_memory()
