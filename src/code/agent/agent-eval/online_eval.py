"""线上评估：OpenTelemetry 记轨迹，规则检查全量跑，裁判按会话抽样，低分进复核队列。

span 名和属性按 OpenTelemetry GenAI 语义约定（目前是 Development 状态）：
invoke_agent / execute_tool / chat 三类操作，gen_ai.* 属性，
评估结果作为 gen_ai.evaluation.result 事件挂在 agent span 上。
本地用内存 exporter，生产换成 OTLP exporter 发到 Langfuse、Phoenix 等后端。
    pip install opentelemetry-sdk
"""

from __future__ import annotations

import hashlib
import time

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from rag_judge import OverlapJudge, faithfulness

exporter = InMemorySpanExporter()
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
tracer = provider.get_tracer("refund-agent")

POLICY = ["质量问题退货，运费由商家承担。", "非质量问题退货，运费由买家承担。"]
FORBIDDEN = ("补贴", "赔偿", "保证")
JUDGE_SAMPLE_RATE = 0.3
review_queue: list[dict] = []


def sampled(conversation_id: str, rate: float) -> bool:
    digest = hashlib.sha256(conversation_id.encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32 < rate


def fake_llm(question: str) -> str:
    if "便宜" in question:
        return "质量问题退货，运费由商家承担。其余情况运费由平台补贴。"
    return "质量问题退货，运费由商家承担。非质量问题退货，运费由买家承担。"


def handle(question: str, conversation_id: str) -> str:
    with tracer.start_as_current_span("invoke_agent refund-agent") as root:
        root.set_attribute("gen_ai.operation.name", "invoke_agent")
        root.set_attribute("gen_ai.agent.name", "refund-agent")
        root.set_attribute("gen_ai.conversation.id", conversation_id)
        start = time.perf_counter()

        with tracer.start_as_current_span("execute_tool search_policy") as tool:
            tool.set_attribute("gen_ai.operation.name", "execute_tool")
            tool.set_attribute("gen_ai.tool.name", "search_policy")
            contexts = POLICY

        with tracer.start_as_current_span("chat gpt-4o-mini") as llm:
            llm.set_attribute("gen_ai.operation.name", "chat")
            llm.set_attribute("gen_ai.provider.name", "openai")
            llm.set_attribute("gen_ai.request.model", "gpt-4o-mini")
            answer = fake_llm(question)
            llm.set_attribute("gen_ai.usage.input_tokens", len(question) + sum(map(len, contexts)))
            llm.set_attribute("gen_ai.usage.output_tokens", len(answer))

        latency_ms = (time.perf_counter() - start) * 1000
        rule_ok = bool(answer) and not any(word in answer for word in FORBIDDEN) and latency_ms < 3000
        root.add_event("gen_ai.evaluation.result", {
            "gen_ai.evaluation.name": "policy_rules",
            "gen_ai.evaluation.score.value": float(rule_ok),
        })

        if not rule_ok or sampled(conversation_id, JUDGE_SAMPLE_RATE):
            score = faithfulness(answer, contexts, OverlapJudge())
            root.add_event("gen_ai.evaluation.result", {
                "gen_ai.evaluation.name": "faithfulness",
                "gen_ai.evaluation.score.value": score,
            })
            if score < 0.8:
                review_queue.append({"conversation_id": conversation_id, "question": question,
                                     "answer": answer, "contexts": contexts, "score": score})
        return answer


if __name__ == "__main__":
    handle("退货运费谁出？", "conv-001")
    handle("能便宜点退吗？", "conv-002")

    spans = exporter.get_finished_spans()
    print([s.name for s in spans])
    agent_spans = [s for s in spans if s.attributes["gen_ai.operation.name"] == "invoke_agent"]
    for span in agent_spans:
        scores = {e.attributes["gen_ai.evaluation.name"]: e.attributes["gen_ai.evaluation.score.value"]
                  for e in span.events}
        print(span.attributes["gen_ai.conversation.id"], scores)

    assert len(spans) == 6
    assert [r["conversation_id"] for r in review_queue] == ["conv-002"]
    assert review_queue[0]["score"] == 0.5
