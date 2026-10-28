"""/memories/ 走 StoreBackend，换一个 thread_id 还能读到。其余路径留在当前线程的 StateBackend。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend


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


def recall_across_threads():
    store = InMemoryStore()
    backend = CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(
                namespace=lambda runtime: ("demo", "filesystem"),
                store=store,
            )
        },
    )
    agent = create_deep_agent(
        model=Scripted(
            calls=[
                (
                    "tool",
                    "write_file",
                    {
                        "file_path": "/memories/AGENTS.md",
                        "content": "prefer short answers",
                    },
                    "a1",
                ),
                (
                    "tool",
                    "write_file",
                    {"file_path": "/notes/scratch.md", "content": "temp"},
                    "a2",
                ),
                ("final", "wrote both"),
                ("tool", "read_file", {"file_path": "/memories/AGENTS.md"}, "b1"),
                ("tool", "read_file", {"file_path": "/notes/scratch.md"}, "b2"),
                ("final", "checked"),
            ]
        ),
        backend=backend,
        checkpointer=InMemorySaver(),
    )
    agent.invoke(
        {"messages": [{"role": "user", "content": "save"}]},
        {"configurable": {"thread_id": "A"}},
    )
    return agent.invoke(
        {"messages": [{"role": "user", "content": "recall"}]},
        {"configurable": {"thread_id": "B"}},
    )


if __name__ == "__main__":
    result = recall_across_threads()
    tool_text = [
        message.content
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    ]
    assert "prefer short answers" in tool_text[0]
    assert "File '/notes/scratch.md' not found" in tool_text[1]
    assert "/notes/scratch.md" not in result["files"]
