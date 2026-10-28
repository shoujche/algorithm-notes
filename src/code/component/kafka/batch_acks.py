"""批量把多次发送收成少数几次写入。acks 决定这次写入要等几个副本。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BatchProducer:
    """字段对应 producer 配置：batch.size、acks。linger.ms 在这里用「攒满再写」表示。"""

    batch_size: int
    acks: str
    replicas: int
    leader: list[str] = field(default_factory=list)
    followers: list[list[str]] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    flushes: int = 0

    def __post_init__(self) -> None:
        if self.acks not in {"0", "1", "all"}:
            raise ValueError("acks must be 0, 1, or all")
        self.followers = [[] for _ in range(self.replicas - 1)]

    def send(self, value: str) -> int | None:
        self.pending.append(value)
        if len(self.pending) >= self.batch_size:
            return self.flush()
        return None

    def flush(self) -> int:
        if not self.pending:
            return 0
        self.flushes += 1
        batch = list(self.pending)
        self.pending.clear()
        # leader 先落。acks=0 时调用方不等副本，所以 follower 先保持落后。
        self.leader.extend(batch)
        if self.acks == "0":
            return 0
        copies = 1 if self.acks == "1" else self.replicas
        for follower in self.followers[: copies - 1]:
            follower.extend(batch)
        return copies


if __name__ == "__main__":
    batched = BatchProducer(batch_size=5, acks="1", replicas=1)
    for index in range(10):
        batched.send(f"m{index}")
    assert batched.flushes == 2
    assert batched.leader == [f"m{index}" for index in range(10)]

    one_by_one = BatchProducer(batch_size=1, acks="1", replicas=1)
    for index in range(10):
        one_by_one.send(f"m{index}")
    assert one_by_one.flushes == 10

    durable = BatchProducer(batch_size=1, acks="all", replicas=3)
    assert durable.send("paid") == 3
    assert durable.leader == ["paid"]
    assert all(copy == ["paid"] for copy in durable.followers)

    fast = BatchProducer(batch_size=1, acks="0", replicas=3)
    assert fast.send("click") == 0
    assert fast.leader == ["click"]
    assert all(copy == [] for copy in fast.followers)
