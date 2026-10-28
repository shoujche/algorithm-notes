"""interrupt_on 让 write_file 先暂停。批准之后，同一条 thread_id 才把文件写进状态。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
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


def approve_plan():
    agent = create_deep_agent(
        model=Scripted(
            calls=[
                (
                    "tool",
                    "write_file",
                    {"file_path": "/notes/plan.md", "content": "ship"},
                    "c1",
                ),
                ("final", "saved"),
            ]
        ),
        interrupt_on={"write_file": True},
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": "t1"}}
    paused = agent.invoke(
        {"messages": [{"role": "user", "content": "write"}]},
        config,
    )
    resumed = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config,
    )
    return paused, resumed


if __name__ == "__main__":
    paused, resumed = approve_plan()
    action = paused["__interrupt__"][0].value["action_requests"][0]
    assert action["name"] == "write_file"
    assert "/notes/plan.md" not in paused["files"]
    assert "/notes/plan.md" in resumed["files"]
    assert any(
        isinstance(message, ToolMessage) and "Updated file /notes/plan.md" in message.content
        for message in resumed["messages"]
    )
    assert resumed["messages"][-1].content == "saved"
