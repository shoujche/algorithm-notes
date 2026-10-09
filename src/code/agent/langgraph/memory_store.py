"""检查点按 thread_id 记住这一条对话。Store 按命名空间跨线程保存。"""

from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_store
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore


class NoteState(TypedDict, total=False):
    hotel: str
    seen: str


def write_note(state: NoteState) -> dict[str, str]:
    get_store().put(("user", "ada"), "hotel", {"name": state["hotel"]})
    return {}


def read_note(state: NoteState) -> dict[str, str]:
    item = get_store().get(("user", "ada"), "hotel")
    return {"seen": item.value["name"]}


def build_writer(store: InMemoryStore):
    graph = StateGraph(NoteState)
    graph.add_node("write_note", write_note)
    graph.add_edge(START, "write_note")
    graph.add_edge("write_note", END)
    return graph.compile(checkpointer=InMemorySaver(), store=store)


def build_reader(store: InMemoryStore):
    graph = StateGraph(NoteState)
    graph.add_node("read_note", read_note)
    graph.add_edge(START, "read_note")
    graph.add_edge("read_note", END)
    return graph.compile(checkpointer=InMemorySaver(), store=store)


def demo() -> None:
    store = InMemoryStore()
    writer = build_writer(store)
    writer.invoke({"hotel": "Ritz"}, {"configurable": {"thread_id": "thread-1"}})
    reader = build_reader(store)
    seen = reader.invoke({}, {"configurable": {"thread_id": "thread-2"}})
    assert seen["seen"] == "Ritz"
    # thread-2 的检查点里没有 thread-1 写下的 hotel，偏好在 Store 里。
    assert "hotel" not in reader.get_state({"configurable": {"thread_id": "thread-2"}}).values
    assert writer.get_state({"configurable": {"thread_id": "thread-1"}}).values["hotel"] == "Ritz"


if __name__ == "__main__":
    demo()
    print("memory_store ok")
