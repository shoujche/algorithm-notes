"""可变默认参数陷阱(mutable default argument)。

坑:默认参数值在"函数定义时"只求值一次,之后所有调用共享同一个默认对象。
如果默认值是可变对象(list/dict/set),多次调用会累积,产生诡异 bug。

正确写法:默认值用 None,在函数体内判断后新建。
"""


def bad_append(item, lst=[]):
    """错误示范:默认 lst=[] 在所有调用间共享同一个 list。"""
    lst.append(item)
    return lst


def good_append(item, lst=None):
    """正确示范:用 None 作哨兵,每次调用新建 list。"""
    if lst is None:
        lst = []
    lst.append(item)
    return lst


if __name__ == "__main__":
    print("=== 错误版本:默认参数被累积 ===")
    print(bad_append(1))  # [1]
    print(bad_append(2))  # [1, 2] —— 竟然带上了上次的!
    print(bad_append(3))  # [1, 2, 3]
    # 因为默认那个 [] 只创建了一次,三次调用都往同一个 list 里塞

    print("\n=== 正确版本:每次独立 ===")
    print(good_append(1))  # [1]
    print(good_append(2))  # [2]
    print(good_append(3))  # [3]

    # 验证:默认对象只在定义时创建一次
    print("\nbad_append 的默认值 id 始终不变:")
    print(id(bad_append.__defaults__[0]))
    bad_append(4)
    print(id(bad_append.__defaults__[0]), "(同一个对象,内容已被污染)")
