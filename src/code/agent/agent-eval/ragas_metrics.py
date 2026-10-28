"""RAGAS 0.4：用 metrics.collections 里的指标给 RAG 样本打分。

0.4 的写法：llm_factory 包一个 OpenAI 客户端，每个指标单独实例化，
调用 ascore 时按关键字传字段。旧版 evaluate(dataset, metrics=[...]) 的教程不再适用。
需要 OPENAI_API_KEY 环境变量；运行会调用模型并产生费用。
    pip install "ragas>=0.4" openai
"""

from __future__ import annotations

import asyncio
import os

from openai import AsyncOpenAI
from ragas.embeddings import OpenAIEmbeddings
from ragas.llms.base import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)

SAMPLES = [
    {
        "user_input": "退货运费谁承担？",
        "retrieved_contexts": [
            "满 99 元订单包邮。",
            "质量问题退货，运费由商家承担。",
            "非质量问题退货，运费由买家承担。",
        ],
        "response": "质量问题退货，运费由商家承担。其余情况运费由平台补贴。",
        "reference": "质量问题退货运费由商家承担；非质量问题退货运费由买家承担。",
    },
]


async def score_sample(sample: dict, metrics: dict) -> dict[str, float]:
    faith, relevancy, precision, recall = await asyncio.gather(
        metrics["faithfulness"].ascore(
            user_input=sample["user_input"],
            response=sample["response"],
            retrieved_contexts=sample["retrieved_contexts"],
        ),
        metrics["answer_relevancy"].ascore(
            user_input=sample["user_input"],
            response=sample["response"],
        ),
        metrics["context_precision"].ascore(
            user_input=sample["user_input"],
            reference=sample["reference"],
            retrieved_contexts=sample["retrieved_contexts"],
        ),
        metrics["context_recall"].ascore(
            user_input=sample["user_input"],
            retrieved_contexts=sample["retrieved_contexts"],
            reference=sample["reference"],
        ),
    )
    return {
        "faithfulness": faith.value,
        "answer_relevancy": relevancy.value,
        "context_precision": precision.value,
        "context_recall": recall.value,
    }


async def main() -> None:
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    judge_model = os.environ.get("EVAL_JUDGE_MODEL", "gpt-4o-mini")
    llm = llm_factory(judge_model, client=client)
    embeddings = OpenAIEmbeddings(client=client, model="text-embedding-3-small")

    metrics = {
        "faithfulness": Faithfulness(llm=llm),
        "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=embeddings),
        "context_precision": ContextPrecisionWithReference(llm=llm),
        "context_recall": ContextRecall(llm=llm),
    }
    for sample in SAMPLES:
        print(sample["user_input"], await score_sample(sample, metrics))


if __name__ == "__main__":
    asyncio.run(main())
