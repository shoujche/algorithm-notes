"""三种切块：固定窗口、重叠窗口、按段落/句子的语义边界打包。"""

import re


def chunk_fixed(text: str, size: int = 80) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size) if text[i : i + size]]


def chunk_overlap(text: str, size: int = 80, overlap: int = 20) -> list[str]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("size > 0 且 0 <= overlap < size")
    step = size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        if start + size >= len(text):
            break
        start += step
    return chunks


_SENTENCE = re.compile(r"(?<=[。！？.!?])\s*")


def chunk_semantic(text: str, max_size: int = 120) -> list[str]:
    """先按空行分段，再按句号切开，尽量在语义边界凑满 max_size。"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sentences: list[str] = []
    for para in paragraphs:
        parts = [s.strip() for s in _SENTENCE.split(para) if s.strip()]
        sentences.extend(parts or [para])

    chunks: list[str] = []
    buf = ""
    for sent in sentences:
        candidate = sent if not buf else f"{buf} {sent}"
        if buf and len(candidate) > max_size:
            chunks.append(buf.strip())
            buf = sent
        else:
            buf = candidate
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


if __name__ == "__main__":
    sample = "RAG 先检索再生成。切块太大容易混主题。\n\n重叠可以保住跨段句子。"
    print(chunk_fixed(sample, 12))
    print(chunk_overlap(sample, 12, 4))
    print(chunk_semantic(sample, 20))
