"""鸭子类型 Duck Typing:不看类型，只看行为(能'嘎嘎叫'就当鸭子)。"""
from typing import Protocol


# —— 经典鸭子类型:不做 isinstance 检查，直接用 ——
class Duck:
    def quack(self) -> str:
        return "嘎嘎"


class Dog:
    def quack(self) -> str:
        return "汪(硬憋出嘎嘎)"


def make_it_quack(thing) -> str:
    # 不关心 thing 是什么类型，只要它有 quack() 方法就行
    return thing.quack()


# —— EAFP 风格:先做，出错再处理(Pythonic) ——
# Easier to Ask Forgiveness than Permission
def get_length_eafp(obj) -> int:
    try:
        return len(obj)          # 直接用，不先问"你支持 len 吗"
    except TypeError:
        return -1


# —— 对比 LBYL 风格:先检查再做(非 Pythonic) ——
# Look Before You Leap
def get_length_lbyl(obj) -> int:
    if hasattr(obj, "__len__"):  # 啰嗦、且有竞态风险
        return len(obj)
    return -1


# —— Protocol:给鸭子类型加"静态类型检查"(structural typing) ——
class Quackable(Protocol):
    def quack(self) -> str: ...


def type_checked_quack(thing: Quackable) -> str:
    # 类型检查器会验证 thing 有 quack()，运行时仍是鸭子类型
    return thing.quack()


if __name__ == "__main__":
    print(make_it_quack(Duck()))  # 嘎嘎
    print(make_it_quack(Dog()))   # 汪(硬憋出嘎嘎) —— 只要有 quack 就行
    print(get_length_eafp([1, 2, 3]))  # 3
    print(get_length_eafp(42))         # -1
