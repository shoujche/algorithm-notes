"""最小 ReAct：Thought → Action → Observation，直到 Finish。模型输出用规则模拟。"""

from __future__ import annotations

import re

from memory import AgentMemory
from tool_registry import ToolRegistry, build_default_registry

ACTION_RE = re.compile(r"^Action:\s*(\w+)\s*(.*)$")
FINISH_RE = re.compile(r"^Finish:\s*(.*)$")


class FakeLLM:
    """面试白板用：按观察结果给出下一步，不调用真实模型。"""

    def __init__(self) -> None:
        self.step = 0

    def complete(self, prompt: str) -> str:
        self.step += 1
        if self.step == 1:
            return "Thought: 需要查天气\nAction: search query=北京天气"
        if "晴" in prompt:
            return "Thought: 已有观察\nFinish: 北京晴，5到18度"
        return "Thought: 工具失败\nFinish: 无法完成"


def parse_action(line: str) -> tuple[str, dict[str, str]]:
    match = ACTION_RE.match(line.strip())
    if not match:
        raise ValueError(f"无法解析动作: {line}")
    name, raw = match.group(1), match.group(2).strip()
    args: dict[str, str] = {}
    for pair in raw.split():
        key, _, value = pair.partition("=")
        args[key] = value
    return name, args


def run_react(
    question: str,
    registry: ToolRegistry | None = None,
    memory: AgentMemory | None = None,
    max_steps: int = 6,
) -> str:
    registry = registry or build_default_registry()
    memory = memory or AgentMemory()
    llm = FakeLLM()
    memory.remember_turn("user", question)
    trace = [f"Question: {question}", memory.prompt_context(question)]

    for _ in range(max_steps):
        output = llm.complete("\n".join(trace))
        trace.append(output)
        last = output.strip().splitlines()[-1]
        finished = FINISH_RE.match(last)
        if finished:
            answer = finished.group(1)
            memory.remember_turn("assistant", answer)
            return answer
        name, args = parse_action(last)
        observation = registry.call(name, **args)
        trace.append(f"Observation: {observation}")
    return "ERROR: max steps exceeded"


if __name__ == "__main__":
    print(run_react("北京天气怎么样？"))
