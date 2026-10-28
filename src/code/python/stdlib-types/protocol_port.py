"""Protocol 只看方法形状。ABC 要求继承，没实现抽象方法时不能实例化。"""

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


class Clock(Protocol):
    def now(self) -> str: ...


class SystemClock:
    def now(self) -> str:
        return "2026-10-16"


class FrozenClock:
    def __init__(self, stamp: str) -> None:
        self._stamp = stamp

    def now(self) -> str:
        return self._stamp


def stamp_note(clock: Clock, text: str) -> str:
    # 参数标成 Clock，两个互不继承的类都能传进来。
    return f"{clock.now()} {text}"


class Store(ABC):
    @abstractmethod
    def save(self, key: str, value: str) -> None: ...


class MemoryStore(Store):
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def save(self, key: str, value: str) -> None:
        self.data[key] = value


class Bag:
    """有 save，但没有继承 Store。"""

    def save(self, key: str, value: str) -> None:
        self.data = {key: value}


class Saver(Protocol):
    def save(self, key: str, value: str) -> None: ...


def persist(saver: Saver, key: str, value: str) -> None:
    saver.save(key, value)


@runtime_checkable
class Closable(Protocol):
    def close(self) -> None: ...


class FileLog:
    def close(self) -> None:
        self.closed = True


if __name__ == "__main__":
    assert stamp_note(SystemClock(), "ok") == "2026-10-16 ok"
    assert stamp_note(FrozenClock("t0"), "ok") == "t0 ok"

    store = MemoryStore()
    persist(store, "a", "1")
    bag = Bag()
    persist(bag, "a", "1")
    assert store.data == {"a": "1"}
    assert bag.data == {"a": "1"}
    assert isinstance(store, Store)
    assert not isinstance(bag, Store)

    try:
        Store()  # type: ignore[abstract]
        raise AssertionError("ABC 缺实现时不能实例化")
    except TypeError:
        pass

    assert isinstance(FileLog(), Closable)
    assert not isinstance(SystemClock(), Closable)
