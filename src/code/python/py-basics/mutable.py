"""可变 vs 不可变对象演示。

Python 里对象分两类:
  - 不可变(immutable):int / float / bool / str / tuple / frozenset —— 值不能原地改
  - 可变(mutable):  list / dict / set —— 可以原地修改内容

核心工具:id() 返回对象的身份(在 CPython 中是内存地址)。
对不可变对象「重新赋值」会指向一个新对象,id 变化;
对可变对象「原地修改」不换对象,id 不变。
"""


def demo_immutable() -> None:
    """不可变对象:任何"修改"其实都是生成新对象。"""
    x = 10
    print("x =", x, "id =", id(x))

    x += 1  # 不是原地 +1,而是新建对象 11 再让 x 指过去
    print("x += 1 ->", x, "id =", id(x), "(id 变了,说明是新对象)")

    s = "hello"
    print("\ns =", s, "id =", id(s))
    s += " world"  # 字符串不可变,拼接产生新字符串
    print("s += ... ->", s, "id =", id(s), "(id 变了)")

    # tuple 不可变:不能对元素赋值
    t = (1, 2, 3)
    try:
        t[0] = 99  # 会抛 TypeError
    except TypeError as e:
        print("\ntuple 不可变,t[0]=99 报错:", e)


def demo_mutable() -> None:
    """可变对象:原地修改,id 不变。"""
    lst = [1, 2, 3]
    print("\nlst =", lst, "id =", id(lst))

    lst.append(4)  # 原地追加,不换对象
    print("append(4) ->", lst, "id =", id(lst), "(id 不变,还是同一个 list)")

    lst2 = lst  # 只是多一个引用,指向同一个对象
    lst2.append(5)
    print("通过 lst2 修改 ->", lst, "(lst 也变了,因为是同一对象)")
    print("lst is lst2 ?", lst is lst2)


def demo_reassign_vs_mutate() -> None:
    """区分"重新赋值"和"原地修改"。"""
    a = [1, 2, 3]
    print("\na =", a, "id =", id(a))

    a = a + [4]  # 重新赋值:新建 list,a 指向新对象
    print("a = a + [4] ->", a, "id =", id(a), "(id 变了,新对象)")

    a += [5]  # 对 list 而言 += 是原地 extend,id 不变
    print("a += [5]    ->", a, "id =", id(a), "(id 不变,原地修改)")


if __name__ == "__main__":
    demo_immutable()
    demo_mutable()
    demo_reassign_vs_mutate()
