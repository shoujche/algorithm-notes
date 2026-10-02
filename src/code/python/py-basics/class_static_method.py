"""staticmethod vs classmethod:重点看 classmethod 的 cls 怎样随调用者变化。"""


class Storage:
    backend = "memory"

    def __init__(self, name):
        self.name = name

    # staticmethod:不收 self 也不收 cls，只是挂在类命名空间里的普通函数
    @staticmethod
    def normalize(name):
        return name.strip().lower()

    # classmethod:第一个参数 cls 是"实际被调用的那个类"
    # 子类调用时 cls 就是子类，所以返回的是子类实例 —— 这就是多态
    @classmethod
    def create(cls, raw_name):
        return cls(cls.normalize(raw_name))

    @classmethod
    def describe(cls):
        return "{} -> {}".format(cls.__name__, cls.backend)

    def __repr__(self):
        return "{}({!r})".format(type(self).__name__, self.name)


class RedisStorage(Storage):
    backend = "redis"  # 只改类属性，create / describe 一行都不用重写


class S3Storage(Storage):
    backend = "s3"

    # 子类可以扩展父类的 classmethod，super() 里 cls 仍然是 S3Storage
    @classmethod
    def create(cls, raw_name):
        storage = super().create(raw_name)
        storage.name = "bucket/" + storage.name
        return storage


# 反例：工厂写成 staticmethod，类名写死，子类调用也只能得到父类
class BrokenStorage(Storage):
    @staticmethod
    def create(raw_name):
        return Storage(Storage.normalize(raw_name))


class BrokenRedis(BrokenStorage):
    backend = "redis"


if __name__ == "__main__":
    print(Storage.normalize("  Cache "))      # cache:类和实例都能调，不依赖任何状态

    for klass in (Storage, RedisStorage, S3Storage):
        obj = klass.create("  Cache ")
        print(obj, klass.describe())
    # Storage('cache') Storage -> memory
    # RedisStorage('cache') RedisStorage -> redis
    # S3Storage('bucket/cache') S3Storage -> s3

    redis = RedisStorage("sessions")
    print(redis.describe())                    # 通过实例调用，cls 仍是 type(redis)

    print(type(BrokenRedis.create("x")).__name__)  # Storage:多态丢了
