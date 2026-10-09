"""create_agent 编出的仍是一张 LangGraph 图：节点是 model 和 tools。不调用真实模型。"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from langgraph.checkpoint.memory import InMemorySaver


@tool
def quote(hotel: str) -> str:
    """查询酒店价格。"""
    return f"{hotel}:420"


class ScriptedModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(message, ToolMessage) for message in messages):
            reply = AIMessage(content="Ritz 报价 420")
        else:
            reply = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "quote",
                        "args": {"hotel": "Ritz"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=reply)])


def build_graph():
    # LangGraph 1.0 起，预置循环从 langgraph.prebuilt.create_react_agent
    # 改到 langchain.agents.create_agent。返回值仍是 CompiledStateGraph。
    return create_agent(
        ScriptedModel(),
        [quote],
        system_prompt="你是预订助手。",
        checkpointer=InMemorySaver(),
    )


def demo() -> None:
    graph = build_graph()
    node_names = set(graph.get_graph().nodes)
    assert {"model", "tools"} <= node_names
    result = graph.invoke(
        {"messages": [HumanMessage("查 Ritz")]},
        {"configurable": {"thread_id": "preset-1"}},
    )
    texts = [message.content for message in result["messages"] if message.content]
    assert "Ritz:420" in texts
    assert texts[-1] == "Ritz 报价 420"


if __name__ == "__main__":
    demo()
    print("preset_agent ok")
