"""参数传递机制:Python 是"传对象引用"(pass by object reference)。

既不是纯粹的"传值",也不是 C++ 的"传引用",而是:
  函数拿到的是实参对象的一个"引用副本"。
  - 如果在函数内"重新赋值"参数名 -> 只改了局部引用,外部看不到。
  - 如果在函数内"原地修改"可变对象 -> 改的是同一个对象,外部能看到。
"""


def try_reassign(x: int) -> None:
    """重新赋值:对不可变对象,外部不受影响。"""
    x = x + 100  # 只是让局部名 x 指向新对象
    print("  函数内 x =", x)


def mutate_list(lst: list) -> None:
    """原地修改可变对象:外部会受影响。"""
    lst.append(999)  # 改的是同一个 list 对象
    print("  函数内 lst =", lst)


def rebind_list(lst: list) -> None:
    """重新赋值参数名:外部看不到。"""
    lst = [-1, -2, -3]  # 局部名指向新 list,原对象没动
    print("  函数内 lst =", lst)


if __name__ == "__main__":
    n = 10
    print("调用前 n =", n)
    try_reassign(n)
    print("调用后 n =", n, "(不变,int 不可变)\n")

    data = [1, 2, 3]
    print("调用前 data =", data)
    mutate_list(data)
    print("调用后 data =", data, "(变了!原地修改同一对象)\n")

    data2 = [1, 2, 3]
    print("调用前 data2 =", data2)
    rebind_list(data2)
    print("调用后 data2 =", data2, "(不变!函数内只是重新绑定了局部名)")
