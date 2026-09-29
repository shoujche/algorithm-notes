"""短期记忆用对话列表；长期记忆用哈希向量做演示检索，不接外部 API。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from math import sqrt


def embed(text: str, dim: int = 16) -> list[float]:
    digest = sha256(text.encode("utf-8")).digest()
    values = [digest[i] / 255.0 for i in range(dim)]
    norm = sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@dataclass
class MemoryItem:
    text: str
    vector: list[float]


class AgentMemory:
    def __init__(self, short_limit: int = 8) -> None:
        self.short: deque[str] = deque(maxlen=short_limit)
        self.long: list[MemoryItem] = []

    def remember_turn(self, role: str, content: str) -> None:
        self.short.append(f"{role}: {content}")

    def save_long(self, text: str) -> None:
        self.long.append(MemoryItem(text=text, vector=embed(text)))

    def recall_long(self, query: str, k: int = 3) -> list[str]:
        qv = embed(query)
        ranked = sorted(self.long, key=lambda item: cosine(qv, item.vector), reverse=True)
        return [item.text for item in ranked[:k]]

    def prompt_context(self, query: str) -> str:
        recent = "\n".join(self.short) or "(空)"
        facts = "\n".join(f"- {text}" for text in self.recall_long(query)) or "- (无)"
        return f"近期对话:\n{recent}\n\n长期记忆:\n{facts}"


if __name__ == "__main__":
    mem = AgentMemory()
    mem.remember_turn("user", "我在北京")
    mem.save_long("用户常驻北京，出差常去上海。")
    print(mem.prompt_context("明天天气"))
