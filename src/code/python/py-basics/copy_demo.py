"""深拷贝 vs 浅拷贝演示。

- 赋值(=)      :不拷贝,只多一个引用,指向同一对象。
- 浅拷贝(copy.copy / list()/切片[:]):新建外层容器,但内部元素仍是"共享引用"。
- 深拷贝(copy.deepcopy)            :递归复制,内部嵌套对象也全部新建,完全独立。

关键:嵌套可变对象(list 里套 list)时,浅拷贝改内层会互相影响,深拷贝不会。
"""

import copy


def demo_shallow() -> None:
    """浅拷贝:外层独立,内层共享。"""
    original = [[1, 2, 3], [4, 5, 6]]
    shallow = copy.copy(original)  # 等价于 original[:] 或 list(original)

    # 外层是新 list,追加不影响原对象
    shallow.append([7, 8, 9])
    print("外层追加后 original =", original, "(不受影响)")

    # 但内层是同一个 list,修改会互相影响!
    shallow[0][0] = 999
    print("内层修改后 original =", original, "(内层被改了!)")
    print("共享内层?", original[0] is shallow[0])


def demo_deep() -> None:
    """深拷贝:内外层全部独立。"""
    original = [[1, 2, 3], [4, 5, 6]]
    deep = copy.deepcopy(original)

    deep[0][0] = 999  # 修改深拷贝的内层
    print("\n深拷贝内层修改后 original =", original, "(完全不受影响)")
    print("共享内层?", original[0] is deep[0])


def demo_assign() -> None:
    """赋值不是拷贝。"""
    original = [[1, 2], [3, 4]]
    alias = original  # 只是别名
    alias[0][0] = 999
    print("\n赋值(别名)后 original =", original, "(当然一起变)")
    print("是同一对象?", original is alias)


if __name__ == "__main__":
    demo_shallow()
    demo_deep()
    demo_assign()
