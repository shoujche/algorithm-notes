"""分区日志和消费组。一个分区在同一组里只分给一个消费者，多出来的消费者空闲。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Record:
    partition: int
    offset: int
    key: str
    value: str


class Topic:
    def __init__(self, partitions: int) -> None:
        self.logs: list[list[Record]] = [[] for _ in range(partitions)]

    def append(self, partition: int, key: str, value: str) -> Record:
        log = self.logs[partition]
        record = Record(partition, len(log), key, value)
        log.append(record)
        return record


def assign(partitions: int, members: list[str]) -> dict[str, list[int]]:
    """Range 分配：按成员名字排序，余数分给前面的成员。"""
    ordered = sorted(members)
    owned = {member: [] for member in ordered}
    if not ordered:
        return owned
    base, extra = divmod(partitions, len(ordered))
    start = 0
    for index, member in enumerate(ordered):
        count = base + (1 if index < extra else 0)
        owned[member] = list(range(start, start + count))
        start += count
    return owned


if __name__ == "__main__":
    topic = Topic(4)
    topic.append(0, "a", "one")
    topic.append(0, "a", "two")
    topic.append(3, "d", "tail")
    assert [item.offset for item in topic.logs[0]] == [0, 1]
    assert topic.logs[3][0].offset == 0

    two = assign(4, ["c1", "c0"])
    assert two == {"c0": [0, 1], "c1": [2, 3]}
    # 消费者比分区多时，多出来的人分不到分区，组的并行度停在分区数。
    three = assign(2, ["c0", "c1", "c2"])
    assert three["c0"] == [0]
    assert three["c1"] == [1]
    assert three["c2"] == []
