"""interrupt(payload) 把 payload 送出去；Command(resume=value) 的 value 变成 interrupt() 的返回值。"""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class BookingState(TypedDict, total=False):
    hotel_name: str
    decision: Any


def human_approval(state: BookingState) -> dict[str, Any]:
    # payload 从节点流向外部，给人看。图在这里暂停。
    decision = interrupt(
        {
            "question": "是否批准这次预订?",
            "hotel_name": state["hotel_name"],
        }
    )
    # decision 就是之后 Command(resume=...) 传进来的那个值，原样回来。
    return {"decision": decision}


def build_graph():
    graph = StateGraph(BookingState)
    graph.add_node("human_approval", human_approval)
    graph.add_edge(START, "human_approval")
    graph.add_edge("human_approval", END)
    # interrupt 必须有 checkpointer，否则无法在暂停后按 thread_id 恢复。
    return graph.compile(checkpointer=InMemorySaver())


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "booking-1"}}
    paused = graph.invoke({"hotel_name": "Ritz"}, config)
    payload = paused["__interrupt__"][0].value
    assert payload == {"question": "是否批准这次预订?", "hotel_name": "Ritz"}

    resume_value = {"type": "edit", "args": {"hotel_name": "McKittrick Hotel"}}
    result = graph.invoke(Command(resume=resume_value), config)
    # 整个字典就是 human_approval 里 decision 变量拿到的值。
    assert result["decision"] == resume_value
    assert result["hotel_name"] == "Ritz"


if __name__ == "__main__":
    demo()
    print("interrupt_resume ok")
