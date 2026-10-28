"""检索阶段的排序指标：Recall@k、Precision@k、Hit Rate、MRR、nDCG。

输入是一次检索返回的有序 id 列表，加上人工标注的相关文档。
切块检索时先把 chunk id 折回文档 id 再算，否则同一篇文档的两块会被算两次。
"""

from __future__ import annotations

import math
import statistics


def to_doc_ids(chunk_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    docs = []
    for chunk in chunk_ids:
        doc = chunk.split("#", 1)[0]
        if doc not in seen:
            seen.add(doc)
            docs.append(doc)
    return docs


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & relevant) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return len(set(retrieved[:k]) & relevant) / k


def hit_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return float(any(doc in relevant for doc in retrieved[:k]))


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], gains: dict[str, float], k: int) -> float:
    dcg = sum(gains.get(doc, 0.0) / math.log2(rank + 1)
              for rank, doc in enumerate(retrieved[:k], start=1))
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(rank + 1) for rank, g in enumerate(ideal, start=1))
    return dcg / idcg if idcg else 0.0


if __name__ == "__main__":
    chunks = ["d3#0", "d1#2", "d1#5", "d7#1", "d2#0", "d9#4"]
    retrieved = to_doc_ids(chunks)
    assert retrieved == ["d3", "d1", "d7", "d2", "d9"]

    relevant = {"d1", "d2"}
    gains = {"d1": 3.0, "d2": 1.0}

    print("recall@3   ", recall_at_k(retrieved, relevant, 3))
    print("recall@5   ", recall_at_k(retrieved, relevant, 5))
    print("precision@3", round(precision_at_k(retrieved, relevant, 3), 3))
    print("RR         ", reciprocal_rank(retrieved, relevant))
    print("nDCG@5     ", round(ndcg_at_k(retrieved, gains, 5), 3))

    assert recall_at_k(retrieved, relevant, 3) == 0.5
    assert recall_at_k(retrieved, relevant, 5) == 1.0
    assert round(precision_at_k(retrieved, relevant, 3), 3) == 0.333
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert round(ndcg_at_k(retrieved, gains, 5), 3) == 0.640

    queries = [
        (retrieved, relevant),
        (["d5", "d6", "d8"], {"d4"}),
    ]
    mrr = statistics.mean(reciprocal_rank(r, rel) for r, rel in queries)
    hit_rate = statistics.mean(hit_at_k(r, rel, 3) for r, rel in queries)
    print("MRR        ", mrr, " HitRate@3", hit_rate)
    assert mrr == 0.25 and hit_rate == 0.5
