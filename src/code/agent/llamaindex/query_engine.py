"""Query engine 先检索，再把节点文本交给 LLM。这里的 LLM 只摘出含价格的那一行。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core import VectorStoreIndex
from llama_index.core.llms import CompletionResponse, CustomLLM, LLMMetadata
from llama_index.core.llms.callbacks import llm_completion_callback

from keyword_embed import KeywordEmbedding, hotel_documents


class QuoteLLM(CustomLLM):
    """不访问网络。prompt 里已经有检索到的原文，挑出含价格的一行当作回答。"""

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(context_window=2048, num_output=256, model_name="quote")

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs) -> CompletionResponse:
        for line in prompt.splitlines():
            if "800" in line or "420" in line:
                return CompletionResponse(text=line.strip())
        return CompletionResponse(text="NO PRICE")

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs):
        text = self.complete(prompt).text
        yield CompletionResponse(text=text, delta=text)


def ask_london() -> str:
    index = VectorStoreIndex.from_documents(
        hotel_documents(),
        embed_model=KeywordEmbedding(),
    )
    # 不传 llm 时，query engine 会去找默认的在线模型。
    response = index.as_query_engine(llm=QuoteLLM(), similarity_top_k=1).query("London")
    assert response.source_nodes[0].node.metadata["hotel"] == "Ritz"
    return response.response


if __name__ == "__main__":
    answer = ask_london()
    assert "800" in answer
    assert "Ritz" in answer
