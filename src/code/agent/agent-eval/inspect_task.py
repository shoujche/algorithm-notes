"""Inspect AI（英国 AISI）：Task = 数据集 + solver + scorer，命令行跑，日志可回放。

epochs 让每题重复多次，reducer 决定怎么合并：mean 看平均，pass_at_2 看两次里至少一次成功。
used_tool 是自定义 scorer，从消息历史里找工具调用。
密钥从环境变量读取（例如 OPENAI_API_KEY），模型在命令行指定：
    pip install "inspect-ai>=0.3"
    inspect eval inspect_task.py --model openai/gpt-4o-mini
    inspect view
"""

from __future__ import annotations

from inspect_ai import Epochs, Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageAssistant
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    accuracy,
    model_graded_qa,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState, generate, system_message, use_tools
from inspect_ai.tool import tool

POLICY = {
    "退货期限": "签收后 7 天内可无理由退货。",
    "退货运费": "质量问题商家承担运费，非质量问题买家承担。",
}


@tool
def search_policy():
    async def execute(topic: str) -> str:
        """查询售后政策。

        Args:
            topic: 政策主题，例如「退货期限」「退货运费」。
        """
        return POLICY.get(topic, "没有找到相关政策。")

    return execute


@scorer(metrics=[accuracy(), stderr()])
def used_tool(name: str = "search_policy"):
    async def score(state: TaskState, target: Target) -> Score:
        called = [
            call.function
            for message in state.messages
            if isinstance(message, ChatMessageAssistant)
            for call in (message.tool_calls or [])
        ]
        return Score(value=CORRECT if name in called else INCORRECT, explanation=str(called))

    return score


@task
def refund_policy() -> Task:
    return Task(
        dataset=[
            Sample(input="东西坏了想退，运费谁出？", target="质量问题由商家承担运费"),
            Sample(input="买了多久之内还能退？", target="签收后 7 天内"),
        ],
        solver=[
            system_message("你是客服。先调用 search_policy 查政策，再回答。"),
            use_tools(search_policy()),
            generate(),
        ],
        scorer=[model_graded_qa(), used_tool()],
        epochs=Epochs(4, ["mean", "pass_at_2"]),
        message_limit=12,
    )
