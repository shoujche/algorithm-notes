"""DeepEval 4.3：把评测写成 pytest 用例，用 `deepeval test run` 跑。

一条 LLMTestCase 装下输入、输出、检索上下文和工具调用；
assert_test 对每个指标比阈值，任一不过就让这条测试失败。
裁判模型默认走 OpenAI，需要 OPENAI_API_KEY 环境变量。
    pip install "deepeval>=4.3"
    deepeval test run test_deepeval_agent.py
"""

from __future__ import annotations

import os

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
    GEval,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall

JUDGE = os.environ.get("EVAL_JUDGE_MODEL", "gpt-4o-mini")

CONTEXTS = [
    "质量问题退货，运费由商家承担。",
    "非质量问题退货，运费由买家承担。",
]


def run_agent(question: str) -> tuple[str, list[ToolCall]]:
    calls = [ToolCall(name="search_policy", input_parameters={"query": "退货 运费"})]
    return "质量问题退货运费由商家承担，非质量问题由买家承担。", calls


@pytest.fixture(scope="module")
def refund_case() -> LLMTestCase:
    answer, calls = run_agent("退货运费谁承担？")
    return LLMTestCase(
        input="退货运费谁承担？",
        actual_output=answer,
        expected_output="质量问题商家承担，非质量问题买家承担。",
        retrieval_context=CONTEXTS,
        tools_called=calls,
        expected_tools=[ToolCall(name="search_policy")],
    )


def test_rag_quality(refund_case: LLMTestCase) -> None:
    assert_test(refund_case, [
        FaithfulnessMetric(threshold=0.8, model=JUDGE),
        AnswerRelevancyMetric(threshold=0.7, model=JUDGE),
        ContextualRecallMetric(threshold=0.7, model=JUDGE),
    ])


def test_tool_use(refund_case: LLMTestCase) -> None:
    assert_test(refund_case, [ToolCorrectnessMetric(threshold=1.0)])


def test_policy_tone(refund_case: LLMTestCase) -> None:
    tone = GEval(
        name="客服口径",
        evaluation_steps=[
            "答案是否只陈述政策，没有承诺政策之外的补偿",
            "答案是否区分了质量问题和非质量问题",
            "出现任一承诺外补偿时直接判 0 分",
        ],
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        threshold=0.7,
        model=JUDGE,
    )
    assert_test(refund_case, [tone])
