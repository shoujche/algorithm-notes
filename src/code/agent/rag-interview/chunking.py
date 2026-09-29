"""带重叠的滑动窗口切块：适合演示 chunk_size / overlap 的取舍。"""


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> list[str]:
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("要求 chunk_size > 0 且 0 <= overlap < chunk_size")

    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
    return chunks


if __name__ == "__main__":
    print(chunk_text("ABCDEFGHIJKLMNOPQRSTUVWXYZ", chunk_size=10, overlap=3))
