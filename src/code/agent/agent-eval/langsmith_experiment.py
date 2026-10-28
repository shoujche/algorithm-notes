"""LangSmith：数据集放在平台上，每次改动跑成一个 experiment，界面里逐条对比。

evaluator 是普通函数，按参数名拿到 inputs / outputs / reference_outputs；
summary_evaluator 看整批结果，适合放通过率之类的汇总指标。
需要环境变量 LANGSMITH_API_KEY；target 里的 agent 换成你自己的调用。
    pip install "langsmith>=0.14"
"""

from __future__ import annotations

from langsmith import Client, traceable

DATASET = "refund-policy-v3"

EXAMPLES = [
    {"inputs": {"question": "退货期限是多久？"},
     "outputs": {"answer": "签收后 7 天内可无理由退货", "must_call": "search_policy"}},
    {"inputs": {"question": "你们的 CEO 是谁？"},
     "outputs": {"answer": "我不确定", "must_call": None}},
]


@traceable(name="refund-agent")
def target(inputs: dict) -> dict:
    question = inputs["question"]
    if "退货" in question:
        return {"answer": "签收后 7 天内可无理由退货", "tool_calls": ["search_policy"]}
    return {"answer": "我不确定", "tool_calls": []}


def correct(outputs: dict, reference_outputs: dict) -> bool:
    return outputs["answer"].strip() == reference_outputs["answer"].strip()


def called_required_tool(outputs: dict, reference_outputs: dict) -> dict:
    required = reference_outputs.get("must_call")
    ok = required is None or required in outputs.get("tool_calls", [])
    return {"key": "required_tool", "score": int(ok)}


def pass_rate(outputs: list[dict], reference_outputs: list[dict]) -> dict:
    hits = sum(correct(o, r) for o, r in zip(outputs, reference_outputs))
    return {"key": "pass_rate", "score": hits / len(outputs)}


if __name__ == "__main__":
    client = Client()
    if not client.has_dataset(dataset_name=DATASET):
        dataset = client.create_dataset(DATASET, description="退货政策问答回归集")
        client.create_examples(dataset_id=dataset.id, examples=EXAMPLES)

    results = client.evaluate(
        target,
        data=DATASET,
        evaluators=[correct, called_required_tool],
        summary_evaluators=[pass_rate],
        experiment_prefix="prompt-v7",
        num_repetitions=3,
        max_concurrency=4,
        metadata={"model": "gpt-4o-mini", "prompt": "v7"},
    )
    print(results.to_pandas()[["inputs.question", "outputs.answer", "feedback.correct"]])
