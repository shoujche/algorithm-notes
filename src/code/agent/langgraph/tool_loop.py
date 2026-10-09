"""模型节点 + ToolNode + tools_condition。工具抛错时写成 ToolMessage，图继续跑。不调用真实模型。"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


@tool
def quote(hotel: str) -> str:
    """查询酒店价格。"""
    return f"{hotel}:420"


@tool
def explode(hotel: str) -> str:
    """会失败的报价。"""
    raise ValueError("下游挂了")


class ScriptedModel(BaseChatModel):
    """按消息内容决定下一步：还没有工具结果就发起调用，有了就收成一句话。"""

    tool_name: str = "quote"

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if any(isinstance(message, ToolMessage) for message in messages):
            reply = AIMessage(content=f"工具说：{messages[-1].content}")
        else:
            reply = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": {"hotel": "Ritz"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=reply)])


def build_graph(tool_name: str):
    model = ScriptedModel(tool_name=tool_name)
    tools = [quote, explode]

    def call_model(state: MessagesState) -> dict[str, list[AIMessage]]:
        return {"messages": [model.invoke(state["messages"])]}

    graph = StateGraph(MessagesState)
    graph.add_node("model", call_model)
    # 默认遇到异常会继续抛。True 表示收成一条 status=error 的 ToolMessage。
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_edge(START, "model")
    # tools_condition：最后一条消息带 tool_calls 就去 tools，否则结束。
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")
    return graph.compile()


def demo() -> None:
    quoted = build_graph("quote").invoke({"messages": [HumanMessage("查 Ritz")]})
    assert quoted["messages"][-1].content == "工具说：Ritz:420"
    failed = build_graph("explode").invoke({"messages": [HumanMessage("查 Ritz")]})
    tool_message = failed["messages"][-2]
    assert tool_message.status == "error"
    assert "下游挂了" in tool_message.content
    assert "下游挂了" in failed["messages"][-1].content


if __name__ == "__main__":
    demo()
    print("tool_loop ok")
