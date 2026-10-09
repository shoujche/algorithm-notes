"""get_state_history 列出检查点。从旧的 checkpoint 改一笔，会在同一条线程上长出新分支。"""

from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class PathState(TypedDict, total=False):
    n: int
    path: str


def step_a(state: PathState) -> dict[str, int | str]:
    return {"n": 1, "path": "a"}


def step_b(state: PathState) -> dict[str, int | str]:
    return {"n": state["n"] + 10, "path": state["path"] + ">b"}


def build_graph():
    graph = StateGraph(PathState)
    graph.add_node("a", step_a)
    graph.add_node("b", step_b)
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    return graph.compile(checkpointer=InMemorySaver())


def demo() -> None:
    graph = build_graph()
    config = {"configurable": {"thread_id": "fork-1"}}
    assert graph.invoke({}, config)["path"] == "a>b"
    finished = graph.get_state(config)
    history = list(graph.get_state_history(config))
    # next == ("b",) 的那一帧是「a 已完成、b 还没跑」。
    before_b = next(snapshot for snapshot in history if snapshot.next == ("b",))
    fork_config = graph.update_state(before_b.config, {"path": "a>fork"})
    assert graph.invoke(None, fork_config)["path"] == "a>fork>b"
    # 不带 checkpoint_id 时，get_state 看到的是这条线程最新的头。
    assert graph.get_state(config).values["path"] == "a>fork>b"
    # 原来的终点还在，用它自己的 config 才能读回 a>b。
    assert graph.get_state(finished.config).values["path"] == "a>b"


if __name__ == "__main__":
    demo()
    print("time_travel ok")
