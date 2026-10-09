"""暂停后用 get_state 看现场，用 update_state 从外面改状态，再 invoke(None) 继续。"""

from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class BookingState(TypedDict, total=False):
    hotel: str
    booked: str


def plan(state: BookingState) -> dict[str, str]:
    return {"hotel": state.get("hotel", "Ritz")}


def execute(state: BookingState) -> dict[str, str]:
    return {"booked": state["hotel"]}


def build_graph():
    graph = StateGraph(BookingState)
    graph.add_node("plan", plan)
    graph.add_node("execute", execute)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", END)
    return graph.compile(checkpointer=InMemorySaver(), interrupt_before=["execute"])


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "edit-1"}}
    graph.invoke({}, config)
    assert graph.get_state(config).values["hotel"] == "Ritz"
    # as_node 表示这次写入看起来像 plan 刚做完。下一步仍是 execute。
    graph.update_state(config, {"hotel": "McKittrick Hotel"}, as_node="plan")
    snapshot = graph.get_state(config)
    assert snapshot.values["hotel"] == "McKittrick Hotel"
    assert snapshot.next == ("execute",)
    assert graph.invoke(None, config)["booked"] == "McKittrick Hotel"


if __name__ == "__main__":
    demo()
    print("update_state ok")
