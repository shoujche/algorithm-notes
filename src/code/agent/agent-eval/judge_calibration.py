"""校准 LLM 裁判：先和人工标注比一致性，再测成对比较的位置偏差。

Cohen's kappa 扣掉了「两边都按各自比例随便标也会撞上」的那部分一致，
所以比原始一致率更能说明裁判是否可信。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal


def cohen_kappa(a: Sequence[int], b: Sequence[int]) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in set(a) | set(b)) / (n * n)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


@dataclass(frozen=True)
class Output:
    name: str
    quality: float


Verdict = Literal["first", "second"]
PairJudge = Callable[[Output, Output], Verdict]


def first_slot_biased(first: Output, second: Output) -> Verdict:
    return "first" if first.quality + 0.5 >= second.quality else "second"


def compare_both_orders(judge: PairJudge, a: Output, b: Output) -> str:
    ab = judge(a, b)
    ba = judge(b, a)
    if ab == "first" and ba == "second":
        return a.name
    if ab == "second" and ba == "first":
        return b.name
    return "tie"


if __name__ == "__main__":
    human = [1, 1, 0, 1, 0, 0, 1, 1, 0, 1]
    judge = [1, 1, 0, 1, 1, 0, 1, 0, 0, 1]
    agreement = sum(x == y for x, y in zip(human, judge)) / len(human)
    kappa = cohen_kappa(human, judge)
    print(f"agreement={agreement:.2f} kappa={kappa:.3f}")
    assert agreement == 0.8
    assert round(kappa, 3) == 0.583

    always_yes = [1] * len(human)
    print("always-yes agreement", sum(x == y for x, y in zip(human, always_yes)) / len(human),
          "kappa", cohen_kappa(human, always_yes))
    assert cohen_kappa(human, always_yes) == 0.0

    pairs = [
        (Output("A", 3.0), Output("B", 3.3)),
        (Output("A", 2.0), Output("B", 4.0)),
        (Output("A", 4.5), Output("B", 2.5)),
    ]
    flips = sum(first_slot_biased(a, b) == first_slot_biased(b, a) for a, b in pairs)
    results = [compare_both_orders(first_slot_biased, a, b) for a, b in pairs]
    print("position flips", flips, "debiased", results)
    assert flips == 1
    assert results == ["tie", "B", "A"]
