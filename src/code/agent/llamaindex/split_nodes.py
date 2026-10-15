"""Document 是原文。SentenceSplitter 把它切成 Node，metadata 复制到每一块。"""

from __future__ import annotations

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter


def split_notes() -> list:
    doc = Document(
        text=(
            "The Ritz in London costs 800 per night. "
            "McKittrick Hotel in New York costs 420 per night."
        ),
        metadata={"source": "notes"},
    )
    # chunk_size 按 token 计，metadata 也占这份预算。
    # 24 刚好把两句切开，又不会从句子中间断开。
    splitter = SentenceSplitter(chunk_size=24, chunk_overlap=0)
    return splitter.get_nodes_from_documents([doc])


if __name__ == "__main__":
    nodes = split_notes()
    texts = [node.get_content() for node in nodes]
    assert texts == [
        "The Ritz in London costs 800 per night.",
        "McKittrick Hotel in New York costs 420 per night.",
    ]
    assert all(node.metadata["source"] == "notes" for node in nodes)
