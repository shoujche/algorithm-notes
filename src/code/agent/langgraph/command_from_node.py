"""从节点 return Command(update=..., goto=...)。这组参数不要拿去当 invoke 的输入。"""

from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


class BookingState(TypedDict, total=False):
    hotel_name: str
    price: int
    decision: str


def quote(state: BookingState) -> dict[str, int]:
    prices = {"Ritz": 800, "McKittrick Hotel": 420}
    return {"price": prices.get(state["hotel_name"], 0)}


def route(state: BookingState) -> Command[Literal["approve", "reject"]]:
    """update 合并状态，goto 跳到指定节点。不必再写条件边。"""
    if state["price"] <= 500:
        return Command(goto="approve", update={"decision": "approved"})
    return Command(goto="reject", update={"decision": "rejected"})


def finish(state: BookingState) -> dict[str, str]:
    return {}


def build_graph():
    graph = StateGraph(BookingState)
    graph.add_node("quote", quote)
    graph.add_node("route", route)
    graph.add_node("approve", finish)
    graph.add_node("reject", finish)
    graph.add_edge(START, "quote")
    graph.add_edge("quote", "route")
    graph.add_edge("approve", END)
    graph.add_edge("reject", END)
    return graph.compile()


def demo() -> None:
    graph = build_graph()
    cheap = graph.invoke({"hotel_name": "McKittrick Hotel"})
    pricey = graph.invoke({"hotel_name": "Ritz"})
    assert cheap["decision"] == "approved"
    assert pricey["decision"] == "rejected"


if __name__ == "__main__":
    demo()
    print("command_from_node ok")
