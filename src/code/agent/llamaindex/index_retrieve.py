"""VectorStoreIndex 把节点和向量放在一起。Retriever 只把节点取回来，不生成答案。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core import VectorStoreIndex

from keyword_embed import KeywordEmbedding, hotel_documents


def retrieve_london():
    # 不传 embed_model 时，Index 会去找默认的在线模型。
    index = VectorStoreIndex.from_documents(
        hotel_documents(),
        embed_model=KeywordEmbedding(),
    )
    return index.as_retriever(similarity_top_k=2).retrieve("London")


if __name__ == "__main__":
    hits = retrieve_london()
    assert hits[0].node.metadata["hotel"] == "Ritz"
    assert "800" in hits[0].node.get_content()
    # top_k=2 会把分数为 0 的另一家也填进来。有没有查到，看分数，不看列表里有没有名字。
    assert hits[0].score > hits[1].score
    assert hits[1].score == 0
