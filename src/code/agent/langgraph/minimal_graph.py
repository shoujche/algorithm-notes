"""最小状态图：状态、节点、条件边、invoke。不调用模型，不读密钥。"""

from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


class BookingState(TypedDict, total=False):
    hotel_name: str
    price: int
    decision: str


def quote(state: BookingState) -> dict[str, int]:
    """节点返回局部更新。没有 reducer 时，同名字段以后一次写入为准。"""
    prices = {"Ritz": 800, "McKittrick Hotel": 420}
    return {"price": prices.get(state["hotel_name"], 0)}


def route(state: BookingState) -> Literal["approve", "reject"]:
    """条件边：函数返回下一个节点的名字。"""
    if state["price"] <= 500:
        return "approve"
    return "reject"


def approve(state: BookingState) -> dict[str, str]:
    return {"decision": "approved"}


def reject(state: BookingState) -> dict[str, str]:
    return {"decision": "rejected"}


def build_graph():
    graph = StateGraph(BookingState)
    graph.add_node("quote", quote)
    graph.add_node("approve", approve)
    graph.add_node("reject", reject)
    graph.add_edge(START, "quote")
    graph.add_conditional_edges("quote", route, ["approve", "reject"])
    graph.add_edge("approve", END)
    graph.add_edge("reject", END)
    return graph.compile()


def demo() -> None:
    graph = build_graph()
    cheap = graph.invoke({"hotel_name": "McKittrick Hotel"})
    pricey = graph.invoke({"hotel_name": "Ritz"})
    assert cheap["decision"] == "approved" and cheap["price"] == 420
    assert pricey["decision"] == "rejected" and pricey["price"] == 800


if __name__ == "__main__":
    demo()
    print("minimal_graph ok")
