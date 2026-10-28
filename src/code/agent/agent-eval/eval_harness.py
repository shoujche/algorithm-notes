"""最小离线评测 harness：数据集 → 被测 agent → 轨迹 → 评估器 → 报告 → CI 门槛。

被测 agent 是一个查表函数，不调模型。接真实 agent 时只替换 run_agent，
其余几层（数据集、评估器、汇总、门槛）保持不变。
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

ABSTAIN = "我不确定"


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    reference: str
    tags: tuple[str, ...] = ()


@dataclass
class Trace:
    case_id: str
    answer: str
    tool_calls: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


@dataclass
class Report:
    scores: dict[str, float]
    by_tag: dict[str, dict[str, float]]
    rows: list[dict]


Evaluator = Callable[[Case, Trace], float]


def run_agent(case: Case) -> Trace:
    start = time.perf_counter()
    kb = {"退货期限": "签收后 7 天内可无理由退货", "运费": "满 99 元包邮"}
    calls: list[str] = []
    answer = ABSTAIN
    for key, value in kb.items():
        if key in case.question:
            calls.append("search_kb")
            answer = value
    return Trace(case.id, answer, calls, (time.perf_counter() - start) * 1000)


def correct(case: Case, trace: Trace) -> float:
    return float(trace.answer.strip() == case.reference.strip())


def used_tool(case: Case, trace: Trace) -> float:
    if "needs_tool" not in case.tags:
        return 1.0
    return float("search_kb" in trace.tool_calls)


def run_suite(cases: list[Case], evaluators: Mapping[str, Evaluator], trials: int = 1) -> Report:
    rows: list[dict] = []
    for case in cases:
        for trial in range(trials):
            trace = run_agent(case)
            row = {"case": case.id, "trial": trial, "tags": case.tags,
                   "answer": trace.answer, "latency_ms": trace.latency_ms}
            for name, fn in evaluators.items():
                row[name] = fn(case, trace)
            rows.append(row)

    scores = {name: statistics.mean(r[name] for r in rows) for name in evaluators}
    by_tag: dict[str, dict[str, float]] = {}
    for tag in sorted({t for c in cases for t in c.tags}):
        tagged = [r for r in rows if tag in r["tags"]]
        by_tag[tag] = {name: statistics.mean(r[name] for r in tagged) for name in evaluators}
    return Report(scores, by_tag, rows)


def gate(report: Report, baseline: Mapping[str, float], max_drop: float = 0.02,
         floors: Mapping[str, float] | None = None) -> list[str]:
    failures = []
    for name, value in report.scores.items():
        if name in baseline and value < baseline[name] - max_drop:
            failures.append(f"{name} 从 {baseline[name]:.2f} 降到 {value:.2f}")
        if floors and name in floors and value < floors[name]:
            failures.append(f"{name}={value:.2f} 低于底线 {floors[name]:.2f}")
    return failures


if __name__ == "__main__":
    cases = [
        Case("c1", "退货期限是多久？", "签收后 7 天内可无理由退货", ("policy", "needs_tool")),
        Case("c2", "运费怎么算？", "满 99 元包邮", ("policy", "needs_tool")),
        Case("c3", "你们的 CEO 是谁？", ABSTAIN, ("unanswerable",)),
        Case("c4", "退货要付运费吗？", "质量问题退货运费由商家承担", ("policy", "needs_tool")),
    ]
    report = run_suite(cases, {"correct": correct, "used_tool": used_tool}, trials=3)

    print("overall", report.scores)
    print("by tag ", {t: round(s["correct"], 3) for t, s in report.by_tag.items()})
    for row in report.rows:
        if row["trial"] == 0 and row["correct"] == 0:
            print("failed ", row["case"], "->", row["answer"])

    assert report.scores == {"correct": 0.75, "used_tool": 1.0}
    assert round(report.by_tag["policy"]["correct"], 3) == 0.667
    assert report.by_tag["unanswerable"]["correct"] == 1.0

    failures = gate(report, baseline={"correct": 0.80, "used_tool": 1.0}, floors={"used_tool": 0.95})
    print("gate   ", failures or "pass")
    assert failures == ["correct 从 0.80 降到 0.75"]
