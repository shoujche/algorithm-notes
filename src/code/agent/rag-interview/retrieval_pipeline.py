"""召回 → 过滤 → 生成前上下文组装的最小骨架。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    text: str
    score: float
    source: str


def prepare_context(hits: list[Hit], threshold: float = 0.65, limit: int = 4) -> str:
    # 生产系统还应做权限过滤、去重、重排和 prompt-injection 检测。
    accepted = [hit for hit in hits if hit.score >= threshold]
    accepted.sort(key=lambda hit: hit.score, reverse=True)
    selected = accepted[:limit]
    return "\n\n".join(
        f"[{index}] 来源：{hit.source}\n{hit.text}"
        for index, hit in enumerate(selected, start=1)
    )


if __name__ == "__main__":
    candidates = [
        Hit("RAG 在生成前检索外部知识。", 0.91, "rag.md"),
        Hit("无关广告文本。", 0.18, "noise.txt"),
    ]
    print(prepare_context(candidates))
