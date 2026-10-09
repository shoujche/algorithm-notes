"""recursion_limit、RetryPolicy、durability、stream。不调用真实模型。"""

from __future__ import annotations

from typing import Literal

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy


class CountState(TypedDict, total=False):
    n: int


def climb(state: CountState) -> dict[str, int]:
    return {"n": state.get("n", 0) + 1}


def route(state: CountState) -> Literal["climb", "__end__"]:
    if state["n"] >= 3:
        return "__end__"
    return "climb"


def build_climb():
    graph = StateGraph(CountState)
    graph.add_node("climb", climb)
    graph.add_edge(START, "climb")
    graph.add_conditional_edges("climb", route)
    return graph.compile()


class TemporaryOutage(Exception):
    """默认重试策略会放过编程错误（RuntimeError、ValueError），这种临时故障才会重试。"""


def build_flaky(attempts: list[int]):
    def flaky(state: CountState) -> dict[str, int]:
        attempts.append(1)
        if len(attempts) < 3:
            raise TemporaryOutage("暂时失败")
        return {"n": 1}

    graph = StateGraph(CountState)
    graph.add_node(
        "flaky",
        flaky,
        retry_policy=RetryPolicy(
            max_attempts=4,
            initial_interval=0.01,
            max_interval=0.01,
            jitter=False,
        ),
    )
    graph.add_edge(START, "flaky")
    graph.add_edge("flaky", END)
    return graph.compile()


class CountingSaver(InMemorySaver):
    def __init__(self) -> None:
        super().__init__()
        self.puts = 0

    def put(self, config, checkpoint, metadata, new_versions):  # type: ignore[override]
        self.puts += 1
        return super().put(config, checkpoint, metadata, new_versions)


def build_two_steps(saver: CountingSaver):
    graph = StateGraph(CountState)
    graph.add_node("a", lambda state: {"n": 1})
    graph.add_node("b", lambda state: {"n": 2})
    graph.add_edge(START, "a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    return graph.compile(checkpointer=saver)


def announce(state: CountState) -> dict[str, int]:
    get_stream_writer()("正在加一")
    return {"n": state.get("n", 0) + 1}


def build_stream():
    graph = StateGraph(CountState)
    graph.add_node("announce", announce)
    graph.add_edge(START, "announce")
    graph.add_edge("announce", END)
    return graph.compile()


def demo() -> None:
    try:
        build_climb().invoke({"n": 0}, {"recursion_limit": 3})
    except GraphRecursionError:
        pass
    else:
        raise AssertionError("步数上限应该截住自循环")
    assert build_climb().invoke({"n": 0}, {"recursion_limit": 20})["n"] == 3

    attempts: list[int] = []
    assert build_flaky(attempts).invoke({"n": 0})["n"] == 1
    assert len(attempts) == 3

    # exit：这次运行结束时写 1 次。sync：每个 superstep 都写。
    # async 表示下一步不必等落盘；InMemorySaver.put 本身立刻返回，所以次数和 sync 一样。
    exit_saver = CountingSaver()
    build_two_steps(exit_saver).invoke(
        {"n": 0},
        {"configurable": {"thread_id": "exit"}},
        durability="exit",
    )
    sync_saver = CountingSaver()
    build_two_steps(sync_saver).invoke(
        {"n": 0},
        {"configurable": {"thread_id": "sync"}},
        durability="sync",
    )
    assert exit_saver.puts == 1
    assert sync_saver.puts > exit_saver.puts

    chunks = list(build_stream().stream({"n": 1}, stream_mode=["updates", "custom"]))
    assert ("custom", "正在加一") in chunks
    assert ("updates", {"announce": {"n": 2}}) in chunks


if __name__ == "__main__":
    demo()
    print("run_controls ok")
