"""graph=Command.PARENT：子图节点把命令发给父图，并跳到父图里的节点。"""

from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command


class NoteState(TypedDict, total=False):
    note: str


def child_node(state: NoteState) -> Command[str]:
    # graph 默认是当前图。PARENT 表示最近的父图。
    return Command(
        graph=Command.PARENT,
        goto="after",
        update={"note": state["note"] + "!"},
    )


def after(state: NoteState) -> dict[str, str]:
    return {"note": state["note"] + " done"}


def build_graph():
    child = StateGraph(NoteState)
    child.add_node("child_node", child_node)
    child.add_edge(START, "child_node")

    parent = StateGraph(NoteState)
    parent.add_node("child", child.compile())
    parent.add_node("after", after)
    parent.add_edge(START, "child")
    parent.add_edge("after", END)
    return parent.compile()


def demo() -> None:
    assert build_graph().invoke({"note": "hello"})["note"] == "hello! done"


if __name__ == "__main__":
    demo()
    print("command_parent ok")
