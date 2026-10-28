"""评测分数的统计：标准误、bootstrap 置信区间、配对比较，以及据此写的 CI 门槛。

40 道题、通过率 70% 时，95% 区间大约是正负 14 个点。
两个版本差 3 个点，在这个规模上分不出来；同一批题配对比较能把噪声压小一些。
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence


def binomial_half_width(p: float, n: int, z: float = 1.96) -> float:
    return z * math.sqrt(p * (1 - p) / n)


def bootstrap_ci(scores: Sequence[float], n_boot: int = 2000, alpha: float = 0.05,
                 seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(scores)
    means = sorted(statistics.mean(rng.choices(scores, k=n)) for _ in range(n_boot))
    return means[int(alpha / 2 * n_boot)], means[int((1 - alpha / 2) * n_boot) - 1]


def paired_diff_ci(base: Sequence[float], cand: Sequence[float], n_boot: int = 2000,
                   alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    diffs = [c - b for b, c in zip(base, cand)]
    low, high = bootstrap_ci(diffs, n_boot, alpha, seed)
    return statistics.mean(diffs), low, high


def regression_gate(base: Sequence[float], cand: Sequence[float], margin: float = 0.0) -> str:
    mean, low, high = paired_diff_ci(base, cand)
    if high < -margin:
        return f"block: 显著变差 {mean:+.3f} [{low:+.3f}, {high:+.3f}]"
    if low > margin:
        return f"ship: 显著变好 {mean:+.3f} [{low:+.3f}, {high:+.3f}]"
    return f"hold: 区间跨过 0，{mean:+.3f} [{low:+.3f}, {high:+.3f}]，加题或多跑几次"


if __name__ == "__main__":
    half = binomial_half_width(0.7, 40)
    print(f"n=40 p=0.70 -> ±{half:.3f}")
    assert round(half, 2) == 0.14

    rng = random.Random(7)
    base = [float(rng.random() < 0.70) for _ in range(300)]
    cand = [float(rng.random() < (0.95 if b else 0.30)) for b in base]

    low, high = bootstrap_ci(base)
    print(f"baseline {statistics.mean(base):.3f} CI=[{low:.3f}, {high:.3f}]")
    print(f"candidate {statistics.mean(cand):.3f}")
    assert low <= statistics.mean(base) <= high

    print("paired   ", regression_gate(base, cand))
    print("first 40 ", regression_gate(base[:40], cand[:40]))
    print("reversed ", regression_gate(cand, base))
    assert regression_gate(base, cand).startswith("ship")
    assert regression_gate(base[:40], cand[:40]).startswith("hold")
    assert regression_gate(cand, base).startswith("block")
