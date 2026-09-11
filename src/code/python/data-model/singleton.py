"""单例模式 Singleton:保证一个类全局只有一个实例。Python 有多种实现。"""
import threading


# ========== 方式一:装饰器版 ==========
def singleton(cls):
    instances = {}
    lock = threading.Lock()

    def get_instance(*args, **kwargs):
        # 双重检查锁定(double-checked locking),兼顾性能与线程安全
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


@singleton
class Config:
    def __init__(self):
        self.data = {}


# ========== 方式二:__new__ 版 ==========
class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    # 注意:__init__ 每次调用仍会执行，需自己加"已初始化"标志防重复初始化


# ========== 方式三:元类版(最彻底，控制类的创建) ==========
class SingletonMeta(type):
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Logger(metaclass=SingletonMeta):
    pass


# ========== 方式四:模块级(最 Pythonic) ==========
# Python 的模块本身就是单例：import 只执行一次，模块级变量天然全局唯一。
# 直接在模块顶层 `default_config = Config()`，别处 import 即拿到同一个对象。


if __name__ == "__main__":
    print(Config() is Config())       # True(装饰器)
    print(Database() is Database())   # True(__new__)
    print(Logger() is Logger())       # True(元类)
