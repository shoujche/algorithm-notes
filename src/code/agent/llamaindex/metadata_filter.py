"""向量负责相似度，metadata 负责硬条件。两边不要互相替代。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import FilterOperator, MetadataFilter, MetadataFilters

from keyword_embed import KeywordEmbedding, hotel_documents


def hotels_open_that_night(city: str) -> list[str]:
    index = VectorStoreIndex.from_documents(
        hotel_documents(),
        embed_model=KeywordEmbedding(),
    )
    # 「per night」两边都命中。城市不是向量能保证的条件，用过滤器拿掉另一座城市。
    filters = MetadataFilters(
        filters=[MetadataFilter(key="city", value=city, operator=FilterOperator.EQ)]
    )
    hits = index.as_retriever(similarity_top_k=2, filters=filters).retrieve("per night")
    return [hit.node.metadata["hotel"] for hit in hits]


if __name__ == "__main__":
    assert hotels_open_that_night("New York") == ["McKittrick"]
    assert hotels_open_that_night("London") == ["Ritz"]
