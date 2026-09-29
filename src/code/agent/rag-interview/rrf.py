"""Reciprocal Rank Fusion：融合 BM25 与向量检索的排序结果。"""

from collections import defaultdict


def reciprocal_rank_fusion(
    rankings: list[list[str]], k: int = 60
) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, document_id in enumerate(ranking, start=1):
            scores[document_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


if __name__ == "__main__":
    bm25 = ["doc-a", "doc-b", "doc-c"]
    vector = ["doc-c", "doc-a", "doc-d"]
    print(reciprocal_rank_fusion([bm25, vector]))
