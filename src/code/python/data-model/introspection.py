"""自省与反射 Introspection:运行时窥探/操作对象的类型、属性与方法。"""
import inspect


class User:
    """一个示例类。"""
    role = "member"

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        return f"hi, {self.name}"


u = User("Ada")

# —— 1. 查类型与继承关系 ——
print(type(u))              # <class '__main__.User'>
print(isinstance(u, User))  # True
print(type(u).__mro__)      # 方法解析顺序(继承链)

# —— 2. 查属性/方法(自省) ——
print(u.__dict__)           # {'name': 'Ada'} —— 实例属性字典
print(dir(u))               # 所有可访问名字(含继承)
print(hasattr(u, "greet"))  # True

# —— 3. 反射:用字符串名动态访问/调用 ——
method = getattr(u, "greet")   # 取出方法对象
print(method())                # hi, Ada
setattr(u, "age", 30)          # 动态设置属性
print(getattr(u, "age"))       # 30
delattr(u, "age")              # 动态删除

# —— 4. 动态调用:根据外部输入决定调哪个方法(如路由分发) ——
action = "greet"
if hasattr(u, action):
    print(getattr(u, action)())  # hi, Ada

# —— 5. inspect:更强的自省(签名、源码、成员) ——
print(inspect.signature(User.__init__))   # (self, name: str)
print(inspect.getmembers(u, inspect.ismethod))  # 所有方法

# 应用:序列化、ORM 字段映射、插件系统、依赖注入,都靠反射。
