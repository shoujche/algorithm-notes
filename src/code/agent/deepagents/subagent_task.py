"""task 把活交给子代理。父代理的消息里只留下最终结论，子代理写的文件会合并回父状态。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from deepagents import create_deep_agent


class Scripted(BaseChatModel):
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


def review_plan():
    # 同一个脚本模型按顺序服务父代理和子代理：先 task，再子代理写草稿并给出结论，最后父代理收口。
    model = Scripted(
        calls=[
            (
                "tool",
                "task",
                {"description": "review the plan", "subagent_type": "reviewer"},
                "t1",
            ),
            (
                "tool",
                "write_file",
                {"file_path": "/scratch/notes.md", "content": "draft line\n" * 20},
                "s1",
            ),
            ("final", "verdict: ship"),
            ("final", "reviewer says ship"),
        ]
    )
    agent = create_deep_agent(
        model=model,
        subagents=[
            {
                "name": "reviewer",
                "description": "Reviews a plan and returns one verdict.",
                "system_prompt": "Return a one-line verdict.",
            }
        ],
    )
    return agent.invoke({"messages": [{"role": "user", "content": "review"}]})


if __name__ == "__main__":
    result = review_plan()
    parent_text = "\n".join(str(message.content) for message in result["messages"])
    task_results = [
        message.content
        for message in result["messages"]
        if isinstance(message, ToolMessage) and message.name == "task"
    ]
    assert task_results == ["verdict: ship"]
    assert "draft line" not in parent_text
    assert "/scratch/notes.md" in result["files"]
    assert result["messages"][-1].content == "reviewer says ship"
