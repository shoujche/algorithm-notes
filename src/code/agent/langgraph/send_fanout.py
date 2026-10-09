"""Send 把一份列表扇成多个 worker。各 worker 的结果用 reducer 叠回父状态。"""

from __future__ import annotations

from operator import add
from typing import Annotated

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send


class JobState(TypedDict):
    items: list[str]
    results: Annotated[list[str], add]


class WorkerInput(TypedDict):
    item: str


def fanout(state: JobState) -> list[Send]:
    return [Send("worker", {"item": item}) for item in state["items"]]


def worker(state: WorkerInput) -> dict[str, list[str]]:
    return {"results": [state["item"].upper()]}


def build_graph():
    graph = StateGraph(JobState)
    graph.add_node("worker", worker)
    graph.add_conditional_edges(START, fanout, ["worker"])
    graph.add_edge("worker", END)
    return graph.compile()


def demo() -> None:
    result = build_graph().invoke({"items": ["ritz", "ada"], "results": []})
    assert sorted(result["results"]) == ["ADA", "RITZ"]


if __name__ == "__main__":
    demo()
    print("send_fanout ok")
