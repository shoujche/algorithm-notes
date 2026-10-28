"""参数标成 collections.abc 里的抽象容器：只读就用 Sequence / Mapping，异步边界用 Callable、Awaitable、AsyncIterator。"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence


def total(nums: Sequence[int]) -> int:
    # Sequence 覆盖 list 和 tuple，函数里只按下标读。
    return sum(nums)


def lookup(table: Mapping[str, int], key: str) -> int:
    return table[key]


def apply(fn: Callable[[int], int], value: int) -> int:
    return fn(value)


async def double_later(value: int) -> int:
    return value * 2


async def await_value(pending: Awaitable[int]) -> int:
    # async def 的调用结果是协程，协程实现了 Awaitable。
    return await pending


async def chunks(text: str) -> AsyncIterator[str]:
    for part in text.split():
        yield part


async def collect(source: AsyncIterator[str]) -> list[str]:
    found: list[str] = []
    async for item in source:
        found.append(item)
    return found


async def main() -> None:
    assert total([1, 2]) == 3
    assert total((1, 2)) == 3
    assert lookup({"a": 1}, "a") == 1
    assert apply(lambda n: n + 1, 2) == 3
    assert await await_value(double_later(4)) == 8
    assert await collect(chunks("alpha beta")) == ["alpha", "beta"]


if __name__ == "__main__":
    asyncio.run(main())
