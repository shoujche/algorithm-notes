"""拿到人类决定之后，用同一次 return 里的 goto 做审批路由。"""

from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class BookingState(TypedDict, total=False):
    decision: str


def human_approval(
    state: BookingState,
) -> Command[Literal["approved_path", "rejected_path"]]:
    decision = interrupt({"question": "批准这次操作吗?"})
    if decision == "yes":
        return Command(goto="approved_path", update={"decision": "approved"})
    return Command(goto="rejected_path", update={"decision": "rejected"})


def finish(state: BookingState) -> dict[str, str]:
    return {}


def build_graph():
    graph = StateGraph(BookingState)
    graph.add_node("human_approval", human_approval)
    graph.add_node("approved_path", finish)
    graph.add_node("rejected_path", finish)
    graph.add_edge(START, "human_approval")
    graph.add_edge("approved_path", END)
    graph.add_edge("rejected_path", END)
    return graph.compile(checkpointer=InMemorySaver())


def demo() -> None:
    approved = build_graph()
    approved_config = {"configurable": {"thread_id": "route-yes"}}
    approved.invoke({}, approved_config)
    assert approved.invoke(Command(resume="yes"), approved_config)["decision"] == "approved"

    rejected = build_graph()
    rejected_config = {"configurable": {"thread_id": "route-no"}}
    rejected.invoke({}, rejected_config)
    assert rejected.invoke(Command(resume="no"), rejected_config)["decision"] == "rejected"


if __name__ == "__main__":
    demo()
    print("approval_route ok")
