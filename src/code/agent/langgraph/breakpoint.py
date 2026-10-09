"""断点停在节点之前。这里没有 interrupt() 在等返回值，恢复用 invoke(None)。"""

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
    # 也可以在某一次 invoke 上临时传 interrupt_before=["execute"]。
    return graph.compile(checkpointer=InMemorySaver(), interrupt_before=["execute"])


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "breakpoint-1"}}
    graph.invoke({}, config)
    snapshot = graph.get_state(config)
    # 断点没有 __interrupt__ payload。next 表示接下来会跑哪个节点。
    assert snapshot.next == ("execute",)
    assert snapshot.interrupts == ()
    assert snapshot.values["hotel"] == "Ritz"
    done = graph.invoke(None, config)
    assert done["booked"] == "Ritz"


if __name__ == "__main__":
    demo()
    print("breakpoint ok")
