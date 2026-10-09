"""恢复时节点从头重跑：interrupt() 之前的代码会再执行一次。"""

from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class BookingState(TypedDict, total=False):
    decision: str


# 故意放在图状态外面，才能看见「暂停前那一行」被执行了几次。
side_effects: list[str] = []


def human_approval(state: BookingState) -> dict[str, str]:
    side_effects.append("即将请求审批")  # 恢复时这行也会再跑一次
    decision = interrupt({"question": "批准吗?"})
    return {"decision": str(decision)}


def build_graph():
    graph = StateGraph(BookingState)
    graph.add_node("human_approval", human_approval)
    graph.add_edge(START, "human_approval")
    graph.add_edge("human_approval", END)
    return graph.compile(checkpointer=InMemorySaver())


def demo() -> None:
    side_effects.clear()
    graph = build_graph()
    config = {"configurable": {"thread_id": "replay-1"}}
    graph.invoke({}, config)
    assert side_effects == ["即将请求审批"]
    result = graph.invoke(Command(resume="yes"), config)
    assert side_effects == ["即将请求审批", "即将请求审批"]
    assert result["decision"] == "yes"


if __name__ == "__main__":
    demo()
    print("replay ok")
