"""MessagesState 用 add_messages 叠加消息。同一个 thread_id 再 invoke，就是接着聊。"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


def echo(state: MessagesState) -> dict[str, list[AIMessage]]:
    last = state["messages"][-1].content
    return {"messages": [AIMessage(content=f"收到:{last}")]}


def build_graph():
    graph = StateGraph(MessagesState)
    graph.add_node("echo", echo)
    graph.add_edge(START, "echo")
    graph.add_edge("echo", END)
    return graph.compile(checkpointer=InMemorySaver())


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "chat-1"}}
    graph.invoke({"messages": [HumanMessage("你好")]}, config)
    graph.invoke({"messages": [HumanMessage("第二句")]}, config)
    texts = [message.content for message in graph.get_state(config).values["messages"]]
    assert texts == ["你好", "收到:你好", "第二句", "收到:第二句"]
    # 换一个 thread_id，就是另一段对话，看不到上面的消息。
    other = graph.invoke(
        {"messages": [HumanMessage("另起一段")]},
        {"configurable": {"thread_id": "chat-2"}},
    )
    assert [message.content for message in other["messages"]] == ["另起一段", "收到:另起一段"]


if __name__ == "__main__":
    demo()
    print("message_thread ok")
