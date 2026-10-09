"""多次 interrupt 怎么对上 resume。列表不会被拆开；并行挂起必须用 interrupt id。"""

from __future__ import annotations

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class FormState(TypedDict, total=False):
    name: str
    city: str


def ask_twice(state: FormState) -> dict[str, str]:
    # 同一个任务里按调用顺序匹配。每次 invoke 只推进下一次还没拿到值的 interrupt。
    name = interrupt("名字?")
    city = interrupt("城市?")
    return {"name": str(name), "city": str(city)}


def build_sequential():
    graph = StateGraph(FormState)
    graph.add_node("ask_twice", ask_twice)
    graph.add_edge(START, "ask_twice")
    graph.add_edge("ask_twice", END)
    return graph.compile(checkpointer=InMemorySaver())


def demo_sequential() -> None:
    graph = build_sequential()
    config = {"configurable": {"thread_id": "form-1"}}
    first = graph.invoke({}, config)
    assert first["__interrupt__"][0].value == "名字?"
    second = graph.invoke(Command(resume="Ada"), config)
    assert second["__interrupt__"][0].value == "城市?"
    done = graph.invoke(Command(resume="London"), config)
    assert done["name"] == "Ada" and done["city"] == "London"


def demo_list_is_one_value() -> None:
    """Command(resume=[a, b]) 把整个列表交给下一次 interrupt，不会按元素拆开。"""
    graph = build_sequential()
    config = {"configurable": {"thread_id": "form-list"}}
    graph.invoke({}, config)
    paused = graph.invoke(Command(resume=["Ada", "London"]), config)
    assert paused["__interrupt__"][0].value == "城市?"


def ask_name(state: FormState) -> dict[str, str]:
    return {"name": str(interrupt("名字?"))}


def ask_city(state: FormState) -> dict[str, str]:
    return {"city": str(interrupt("城市?"))}


def join(state: FormState) -> dict[str, str]:
    return {}


def build_parallel():
    graph = StateGraph(FormState)
    graph.add_node("ask_name", ask_name)
    graph.add_node("ask_city", ask_city)
    graph.add_node("join", join)
    graph.add_edge(START, "ask_name")
    graph.add_edge(START, "ask_city")
    graph.add_edge("ask_name", "join")
    graph.add_edge("ask_city", "join")
    graph.add_edge("join", END)
    return graph.compile(checkpointer=InMemorySaver())


def demo_parallel() -> None:
    graph = build_parallel()
    config = {"configurable": {"thread_id": "form-parallel"}}
    paused = graph.invoke({}, config)
    pending = paused["__interrupt__"]
    assert len(pending) == 2
    try:
        graph.invoke(Command(resume="only-one"), config)
        raise AssertionError("多个 pending interrupt 时，单个 resume 值应该被拒绝")
    except RuntimeError as exc:
        assert "interrupt id" in str(exc)
    resume_map = {item.id: f"ok:{item.value}" for item in pending}
    done = graph.invoke(Command(resume=resume_map), config)
    assert done["name"] == "ok:名字?"
    assert done["city"] == "ok:城市?"


def demo() -> None:
    demo_sequential()
    demo_list_is_one_value()
    demo_parallel()


if __name__ == "__main__":
    demo()
    print("multi_interrupt ok")
