"""生成阶段的 RAG 指标：faithfulness、context precision、context recall。

算法和 RAGAS 的定义一致：先把答案或参考答案拆成陈述，再逐条问裁判
「这条能不能由检索到的上下文推出」。裁判是可替换的：
- OverlapJudge 用字符二元组重合度，离线可跑，只适合演示；
- LLMJudge 把同样的问题交给模型，客户端由调用方创建，密钥从环境变量读取。
"""

from __future__ import annotations

import re
from typing import Protocol

PUNCT = re.compile(r"[\s，。！？；、,.!?;]")


class Judge(Protocol):
    def supported(self, claim: str, contexts: list[str]) -> bool: ...


def split_claims(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?]", text) if part.strip()]


def bigrams(text: str) -> set[str]:
    text = PUNCT.sub("", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


class OverlapJudge:
    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def supported(self, claim: str, contexts: list[str]) -> bool:
        grams = bigrams(claim)
        if not grams:
            return False
        best = max(len(grams & bigrams(c)) / len(grams) for c in contexts)
        return best >= self.threshold


SUPPORT_PROMPT = """你是评测裁判。只根据【上下文】判断【陈述】是否成立。
上下文没有提到或与之矛盾，都回答 no。只输出 yes 或 no。

【上下文】
{contexts}

【陈述】
{claim}"""


class LLMJudge:
    def __init__(self, client, model: str) -> None:
        self.client = client
        self.model = model

    def supported(self, claim: str, contexts: list[str]) -> bool:
        prompt = SUPPORT_PROMPT.format(contexts="\n---\n".join(contexts), claim=claim)
        reply = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return reply.choices[0].message.content.strip().lower().startswith("yes")


def faithfulness(answer: str, contexts: list[str], judge: Judge) -> float:
    claims = split_claims(answer)
    if not claims:
        return 0.0
    return sum(judge.supported(c, contexts) for c in claims) / len(claims)


def context_precision(contexts: list[str], reference: str, judge: Judge) -> float:
    verdicts = [judge.supported(c, [reference]) for c in contexts]
    hits, total = 0, 0.0
    for k, useful in enumerate(verdicts, start=1):
        if useful:
            hits += 1
            total += hits / k
    return total / hits if hits else 0.0


def context_recall(reference: str, contexts: list[str], judge: Judge) -> float:
    claims = split_claims(reference)
    if not claims:
        return 0.0
    return sum(judge.supported(c, contexts) for c in claims) / len(claims)


if __name__ == "__main__":
    contexts = [
        "满 99 元订单包邮。",
        "质量问题退货，运费由商家承担。",
        "非质量问题退货，运费由买家承担。",
    ]
    reference = "质量问题退货运费由商家承担。非质量问题退货运费由买家承担。"
    answer = "质量问题退货，运费由商家承担。其余情况运费由平台补贴。"

    judge = OverlapJudge()
    f = faithfulness(answer, contexts, judge)
    cp = context_precision(contexts, reference, judge)
    cr = context_recall(reference, contexts, judge)
    print(f"faithfulness={f:.2f} context_precision={cp:.3f} context_recall={cr:.2f}")

    assert f == 0.5
    assert round(cp, 3) == 0.583
    assert cr == 1.0

    reordered = [contexts[1], contexts[2], contexts[0]]
    assert context_precision(reordered, reference, judge) == 1.0
