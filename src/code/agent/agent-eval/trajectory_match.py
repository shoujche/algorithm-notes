"""工具调用与轨迹评测：逐步比对、五种匹配模式、pass@k 与 pass^k。

匹配模式的命名参考 LangChain agentevals（strict / unordered / subset / superset），
另加 in_order：期望的调用按顺序出现即可，中间允许多出别的调用。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from math import comb
from typing import Literal

Mode = Literal["strict", "in_order", "unordered", "subset", "superset"]


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict = field(default_factory=dict, hash=False)

    def key(self, ignore: frozenset[str] = frozenset()) -> tuple:
        kept = {k: v for k, v in self.args.items() if k not in ignore}
        return (self.name, tuple(sorted(kept.items())))


def match(actual: list[ToolCall], expected: list[ToolCall], mode: Mode,
          ignore: frozenset[str] = frozenset()) -> bool:
    a = [c.key(ignore) for c in actual]
    e = [c.key(ignore) for c in expected]
    if mode == "strict":
        return a == e
    if mode == "in_order":
        it = iter(a)
        return all(step in it for step in e)
    if mode == "unordered":
        return Counter(a) == Counter(e)
    if mode == "subset":
        return not (Counter(a) - Counter(e))
    if mode == "superset":
        return not (Counter(e) - Counter(a))
    raise ValueError(mode)


def tool_selection(actual: list[ToolCall], expected: list[ToolCall]) -> tuple[float, float]:
    got = Counter(c.name for c in actual)
    want = Counter(c.name for c in expected)
    hit = sum((got & want).values())
    precision = hit / sum(got.values()) if got else 0.0
    recall = hit / sum(want.values()) if want else 1.0
    return precision, recall


def pass_at_k(n: int, c: int, k: int) -> float:
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    return comb(c, k) / comb(n, k)


if __name__ == "__main__":
    search = ToolCall("search_flights", {"from": "SHA", "to": "PEK", "date": "2026-11-02"})
    book = ToolCall("book_flight", {"flight_id": "MU5101", "request_id": "r-17"})
    expected = [search, ToolCall("book_flight", {"flight_id": "MU5101", "request_id": "r-01"})]
    actual = [ToolCall("get_user", {"user_id": "u1"}), search, book]

    ignore = frozenset({"request_id"})
    verdicts = {m: match(actual, expected, m, ignore) for m in
                ("strict", "in_order", "unordered", "subset", "superset")}
    print("modes    ", verdicts)
    assert verdicts == {"strict": False, "in_order": True, "unordered": False,
                        "subset": False, "superset": True}
    assert not match(actual, expected, "in_order")

    p, r = tool_selection(actual, expected)
    print(f"selection precision={p:.3f} recall={r:.1f}")
    assert round(p, 3) == 0.667 and r == 1.0

    n, c = 8, 6
    print(f"pass@1={pass_at_k(n, c, 1):.2f} pass@4={pass_at_k(n, c, 4):.2f} "
          f"pass^4={pass_hat_k(n, c, 4):.3f}")
    assert pass_at_k(n, c, 1) == pass_hat_k(n, c, 1) == 0.75
    assert pass_at_k(n, c, 4) == 1.0
    assert round(pass_hat_k(n, c, 4), 3) == 0.214
