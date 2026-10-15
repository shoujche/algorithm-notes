"""用词是否出现来当向量。不调用 embedding API，也不读密钥。

生产环境把这个类换成真实 embedding 模型，后面的 Index 调用不用改。
维度顺序固定，方便断言。
"""

from __future__ import annotations

from llama_index.core import Document
from llama_index.core.embeddings import BaseEmbedding

# 每一维是一个词。查询和原文都按小写做子串匹配。
KEYS: tuple[str, ...] = (
    "london",
    "new york",
    "ritz",
    "mckittrick",
    "800",
    "420",
    "night",
)


class KeywordEmbedding(BaseEmbedding):
    """命中的词记 1，其余记 0。余弦相似度就变成两边共有哪些词。"""

    def _vector(self, text: str) -> list[float]:
        lowered = text.lower()
        return [1.0 if key in lowered else 0.0 for key in KEYS]

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)


def hotel_documents() -> list[Document]:
    """两家酒店各一份 Document。metadata 不进向量，留给后面的过滤。"""
    return [
        Document(
            text="The Ritz in London costs 800 per night.",
            metadata={"city": "London", "hotel": "Ritz"},
        ),
        Document(
            text="McKittrick Hotel in New York costs 420 per night.",
            metadata={"city": "New York", "hotel": "McKittrick"},
        ),
    ]


if __name__ == "__main__":
    embed = KeywordEmbedding()
    vector = dict(zip(KEYS, embed.get_query_embedding("London night"), strict=True))
    assert vector["london"] == 1.0
    assert vector["new york"] == 0.0
    assert vector["night"] == 1.0
    docs = hotel_documents()
    assert docs[0].metadata["hotel"] == "Ritz"
    assert "420" in docs[1].text
