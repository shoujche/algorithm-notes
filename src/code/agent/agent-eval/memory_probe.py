"""记忆评测：按能力分类出题，每类单独计分。

题型借鉴 LongMemEval：信息抽取、跨会话汇总、知识更新、时间推理、拒答。
两套记忆实现跑同一份题：
- NaiveMemory 像只做相似度检索的向量库，永远返回一条，不看时间；
- VersionedMemory 给每个槽位留带日期的版本，能回答「现在」和「当时」。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal, Protocol

Kind = Literal["extraction", "multi_session", "update", "temporal", "abstention"]


class Memory(Protocol):
    def write(self, day: int, slot: str, value: str) -> None: ...
    def read(self, slot: str, as_of: int | None = None) -> str | None: ...
    def history(self, slot: str) -> list[str]: ...


class NaiveMemory:
    def __init__(self) -> None:
        self.facts: list[tuple[int, str, str]] = []

    def write(self, day: int, slot: str, value: str) -> None:
        self.facts.append((day, slot, value))

    def read(self, slot: str, as_of: int | None = None) -> str | None:
        for _, s, value in self.facts:
            if s == slot:
                return value
        return self.facts[-1][2] if self.facts else None

    def history(self, slot: str) -> list[str]:
        return list(dict.fromkeys(v for _, s, v in self.facts if s == slot))


class VersionedMemory:
    def __init__(self) -> None:
        self.versions: dict[str, list[tuple[int, str]]] = defaultdict(list)

    def write(self, day: int, slot: str, value: str) -> None:
        self.versions[slot].append((day, value))
        self.versions[slot].sort()

    def read(self, slot: str, as_of: int | None = None) -> str | None:
        found = None
        for day, value in self.versions.get(slot, []):
            if as_of is None or day <= as_of:
                found = value
        return found

    def history(self, slot: str) -> list[str]:
        return list(dict.fromkeys(v for _, v in self.versions.get(slot, [])))


@dataclass(frozen=True)
class Probe:
    kind: Kind
    question: str
    slot: str
    expected: str | None
    as_of: int | None = None
    count: bool = False


SESSIONS = [
    (1, "city", "上海"), (1, "pet", "猫"),
    (10, "employer", "A 公司"),
    (30, "city", "杭州"),
    (40, "employer", "B 公司"),
]

PROBES = [
    Probe("extraction", "我养的是什么宠物？", "pet", "猫"),
    Probe("multi_session", "我一共住过几个城市？", "city", "2", count=True),
    Probe("update", "我现在住在哪？", "city", "杭州"),
    Probe("temporal", "第 20 天时我住在哪？", "city", "上海", as_of=20),
    Probe("abstention", "我开什么车？", "car", None),
]


def answer(memory: Memory, probe: Probe) -> str | None:
    if probe.count:
        return str(len(memory.history(probe.slot)))
    return memory.read(probe.slot, probe.as_of)


def evaluate(memory: Memory) -> dict[str, float]:
    for day, slot, value in SESSIONS:
        memory.write(day, slot, value)
    scores: dict[str, list[float]] = defaultdict(list)
    for probe in PROBES:
        scores[probe.kind].append(float(answer(memory, probe) == probe.expected))
    return {kind: sum(v) / len(v) for kind, v in scores.items()}


if __name__ == "__main__":
    naive = evaluate(NaiveMemory())
    versioned = evaluate(VersionedMemory())
    print("naive    ", naive)
    print("versioned", versioned)

    assert naive == {"extraction": 1.0, "multi_session": 1.0, "update": 0.0,
                     "temporal": 1.0, "abstention": 0.0}
    assert all(score == 1.0 for score in versioned.values())
