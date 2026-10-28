"""先处理再提交位点。崩溃后从上次提交的 offset 再读，所以同一条可能处理两次。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PartitionConsumer:
    log: list[str]
    position: int = 0
    committed: int = 0
    handled: list[str] = field(default_factory=list)

    def poll(self) -> str | None:
        if self.position >= len(self.log):
            return None
        value = self.log[self.position]
        self.position += 1
        return value

    def handle(self, value: str) -> None:
        self.handled.append(value)

    def commit(self) -> None:
        self.committed = self.position

    def crash(self) -> None:
        # 未提交的进度丢掉，下次从 committed 接着读。
        self.position = self.committed


def commit_watermark(done: set[int], committed: int) -> int:
    """并发处理同一分区时，只能提交连续完成的最大位点。"""
    cursor = committed
    while cursor in done:
        cursor += 1
    return cursor


if __name__ == "__main__":
    consumer = PartitionConsumer(["a", "b", "c"])
    first = consumer.poll()
    assert first == "a"
    consumer.handle(first)
    consumer.crash()
    assert consumer.poll() == "a"
    consumer.handle("a")
    consumer.commit()
    assert consumer.poll() == "b"
    consumer.handle("b")
    consumer.commit()
    consumer.crash()
    assert consumer.poll() == "c"
    assert consumer.handled == ["a", "a", "b"]

    # 0 和 2 先完成，1 还在跑。位点停在 0，避免把 1 标成已完成。
    assert commit_watermark({0, 2}, 0) == 1
    assert commit_watermark({0, 1, 2}, 0) == 3
