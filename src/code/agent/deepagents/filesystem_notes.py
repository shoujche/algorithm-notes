"""create_deep_agent 自带虚拟文件系统。脚本模型写入 /notes/plan.md，文件留在当前线程的状态里。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from deepagents import create_deep_agent


class Scripted(BaseChatModel):
    """按事先排好的步骤回复，不调用模型 API。"""

    calls: list

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        step = self.calls.pop(0)
        if step[0] == "tool":
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": step[1],
                        "args": step[2],
                        "id": step[3],
                        "type": "tool_call",
                    }
                ],
            )
        else:
            message = AIMessage(content=step[1])
        return ChatResult(generations=[ChatGeneration(message=message)])


def write_plan():
    agent = create_deep_agent(
        model=Scripted(
            calls=[
                (
                    "tool",
                    "write_file",
                    {"file_path": "/notes/plan.md", "content": "ship it"},
                    "c1",
                ),
                ("tool", "read_file", {"file_path": "/notes/plan.md"}, "c2"),
                ("final", "wrote the plan"),
            ]
        ),
        system_prompt="keep notes on the virtual disk",
    )
    return agent.invoke({"messages": [{"role": "user", "content": "write a plan"}]})


if __name__ == "__main__":
    result = write_plan()
    tool_text = [
        message.content
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    ]
    assert any("Updated file /notes/plan.md" in text for text in tool_text)
    assert any("ship it" in text for text in tool_text)
    assert "/notes/plan.md" in result["files"]
    assert result["messages"][-1].content == "wrote the plan"
