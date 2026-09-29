"""把相关性与时间新鲜度组合，避免旧内容长期霸榜。"""

from dataclasses import dataclass
from math import exp


@dataclass(frozen=True)
class Candidate:
    document_id: str
    relevance: float
    age_days: float


def rank_with_time_decay(
    candidates: list[Candidate], decay: float = 0.02, freshness_weight: float = 0.25
) -> list[tuple[str, float]]:
    ranked = []
    for item in candidates:
        freshness = exp(-decay * max(item.age_days, 0))
        score = (1 - freshness_weight) * item.relevance + freshness_weight * freshness
        ranked.append((item.document_id, score))
    return sorted(ranked, key=lambda item: item[1], reverse=True)


if __name__ == "__main__":
    docs = [Candidate("old-good", 0.95, 365), Candidate("new-good", 0.88, 2)]
    print(rank_with_time_decay(docs))
