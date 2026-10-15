"""Workflow 把检索和作答分成两步。循环、暂停仍交给 LangGraph，不在这里重做。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core import VectorStoreIndex
from llama_index.core.workflow import Event, StartEvent, StopEvent, Workflow, step

from keyword_embed import KeywordEmbedding, hotel_documents


class Retrieved(Event):
    hotel: str
    text: str


class HotelFlow(Workflow):
    @step
    async def retrieve(self, ev: StartEvent) -> Retrieved:
        index = VectorStoreIndex.from_documents(
            hotel_documents(),
            embed_model=KeywordEmbedding(),
        )
        hit = index.as_retriever(similarity_top_k=1).retrieve(ev.question)[0]
        return Retrieved(hotel=hit.node.metadata["hotel"], text=hit.node.get_content())

    @step
    async def answer(self, ev: Retrieved) -> StopEvent:
        # 这一步在生产里调用 query engine 或真实模型。这里直接从原文摘价格。
        price = "800" if "800" in ev.text else "420"
        return StopEvent(result=f"{ev.hotel}:{price}")


async def ask(question: str) -> str:
    # run() 内部要创建 task，所以必须在已经跑起来的事件循环里调用。
    handler = HotelFlow(timeout=15).run(question=question)
    return await handler


if __name__ == "__main__":
    assert asyncio.run(ask("London")) == "Ritz:800"
