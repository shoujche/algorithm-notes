"""IngestionPipeline 把切块和向量写成一条显式流水线。from_documents 把这两步藏起来了。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter

from keyword_embed import KEYS, KeywordEmbedding, hotel_documents


def run_pipeline():
    pipeline = IngestionPipeline(
        transformations=[
            SentenceSplitter(chunk_size=128, chunk_overlap=0),
            KeywordEmbedding(),
        ]
    )
    return pipeline.run(documents=hotel_documents())


if __name__ == "__main__":
    nodes = run_pipeline()
    assert len(nodes) == 2
    assert nodes[0].embedding is not None
    assert len(nodes[0].embedding) == len(KEYS)
    assert {node.metadata["hotel"] for node in nodes} == {"Ritz", "McKittrick"}
