"""FilesystemPermission 按顺序匹配。/private/** 先拒绝写入，其余路径再允许。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from deepagents import create_deep_agent
from deepagents.middleware.filesystem import FilesystemPermission


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


def save_two_paths():
    agent = create_deep_agent(
        model=Scripted(
            calls=[
                (
                    "tool",
                    "write_file",
                    {"file_path": "/private/draft.md", "content": "unreleased"},
                    "c1",
                ),
                (
                    "tool",
                    "write_file",
                    {"file_path": "/notes/ok.md", "content": "public"},
                    "c2",
                ),
                ("final", "done"),
            ]
        ),
        permissions=[
            FilesystemPermission(
                operations=["write"],
                paths=["/private/**"],
                mode="deny",
            ),
            FilesystemPermission(
                operations=["write"],
                paths=["/**"],
                mode="allow",
            ),
        ],
    )
    return agent.invoke({"messages": [{"role": "user", "content": "save both"}]})


if __name__ == "__main__":
    result = save_two_paths()
    tool_text = [
        message.content
        for message in result["messages"]
        if isinstance(message, ToolMessage)
    ]
    assert "Error: permission denied for write on /private/draft.md" in tool_text[0]
    assert "Updated file /notes/ok.md" in tool_text[1]
    assert "/private/draft.md" not in result["files"]
    assert "/notes/ok.md" in result["files"]
