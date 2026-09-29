"""Top-P（Nucleus）采样：按累积概率动态决定候选集合。"""

from itertools import accumulate


def nucleus_sample(probs: dict[str, float], p: float = 0.9) -> list[str]:
    ranked = sorted(probs.items(), key=lambda item: item[1], reverse=True)
    cutoff = 0
    for index, total in enumerate(accumulate(score for _, score in ranked), start=1):
        cutoff = index
        if total >= p:
            break
    return [token for token, _ in ranked[:cutoff]]


if __name__ == "__main__":
    print(nucleus_sample({"是": 0.62, "对": 0.21, "可能": 0.11, "啊": 0.06}))
