"""工具注册表：按名字查找、校验参数、统一执行入口。"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., str]
    required: tuple[str, ...] = ()


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def schema_for_prompt(self) -> str:
        lines = []
        for spec in self._tools.values():
            req = ", ".join(spec.required) or "无"
            lines.append(f"- {spec.name}: {spec.description}；必填参数: {req}")
        return "\n".join(lines)

    def call(self, name: str, **kwargs: Any) -> str:
        spec = self._tools.get(name)
        if spec is None:
            return f"ERROR: unknown tool {name}"
        missing = [key for key in spec.required if key not in kwargs]
        if missing:
            return f"ERROR: missing args {missing}"
        return spec.handler(**kwargs)


def search(query: str) -> str:
    catalog = {
        "北京天气": "晴，5到18度",
        "上海天气": "小雨，12到16度",
    }
    return catalog.get(query, f"未找到: {query}")


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec("search", "按关键词查询内部知识", search, required=("query",))
    )
    return registry


if __name__ == "__main__":
    tools = build_default_registry()
    print(tools.call("search", query="北京天气"))
