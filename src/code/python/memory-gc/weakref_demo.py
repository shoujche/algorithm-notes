"""弱引用：weakref 不增加引用计数，对象仍可被正常回收，适合做缓存避免内存泄漏。"""
import weakref


class Image:
    def __init__(self, name: str) -> None:
        self.name = name

    def __del__(self) -> None:
        print(f"Image {self.name} 被回收")


def basic() -> None:
    img = Image("cat.png")
    ref = weakref.ref(img)  # 弱引用，不增加 img 的引用计数

    print("弱引用取对象:", ref().name)  # 调用 ref() 拿到强引用

    del img  # 唯一强引用消失 → 对象立即回收
    print("del 后弱引用:", ref())  # None，说明对象已被回收


def cache_demo() -> None:
    """WeakValueDictionary：值被弱引用持有，无人使用时自动从缓存中消失，
    从而避免缓存把对象永久钉在内存里（内存泄漏）。"""
    cache: "weakref.WeakValueDictionary[str, Image]" = weakref.WeakValueDictionary()

    img = Image("dog.png")
    cache["dog"] = img  # 缓存不持有强引用
    print("缓存命中:", cache.get("dog"))

    del img  # 外部强引用消失 → 缓存条目自动清除
    print("释放后缓存:", cache.get("dog"))  # None


if __name__ == "__main__":
    basic()
    print("-" * 20)
    cache_demo()
