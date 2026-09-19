from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


class MCPToolClient:
    """Adapt an initialized MCP ClientSession to Responses function tools."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def list_function_tools(self) -> list[dict[str, Any]]:
        listed = await self._session.list_tools()
        tools: list[dict[str, Any]] = []
        for tool in listed.tools:
            if not isinstance(tool.inputSchema, Mapping) or tool.inputSchema.get(
                "type"
            ) != "object":
                raise ValueError(
                    f"tool {tool.name} function parameter root must be object"
                )
            parameters = _strict_schema(tool.inputSchema, f"tool {tool.name}")
            tools.append(
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": parameters,
                    "strict": True,
                }
            )
        return validate_function_tools(tools)

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        result = await self._session.call_tool(name, arguments)
        if result.structuredContent is not None:
            content: Any = result.structuredContent
        else:
            content = [_content_value(item) for item in result.content]
        payload = {
            "is_error": bool(result.isError),
            "content": content,
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def validate_function_tools(
    definitions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate the strict function-tool contract shared by every agent layer."""
    validated: list[dict[str, Any]] = []
    names: set[str] = set()
    for definition in definitions:
        if not isinstance(definition, Mapping):
            raise ValueError("function tool definition must be an object")
        name = definition.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("function tool name must be a non-empty string")
        if name in names:
            raise ValueError(f"function tool names must be unique: {name!r}")
        names.add(name)
        if definition.get("type") != "function":
            raise ValueError(f"tool {name!r} must have type 'function'")
        if definition.get("strict") is not True:
            raise ValueError(f"function schema for {name!r} must be strict")
        schema = definition.get("parameters")
        if not isinstance(schema, Mapping) or schema.get("type") != "object":
            raise ValueError(
                f"tool {name} function parameter root must be object"
            )
        normalized = dict(definition)
        normalized["parameters"] = _strict_schema(schema, f"tool {name}")
        validated.append(normalized)
    return validated


_TYPE_KEYS = {
    "string": frozenset(
        {"type", "description", "enum", "const", "minLength", "maxLength", "pattern"}
    ),
    "number": frozenset(
        {"type", "description", "enum", "const", "minimum", "maximum"}
    ),
    "integer": frozenset(
        {"type", "description", "enum", "const", "minimum", "maximum"}
    ),
    "boolean": frozenset({"type", "description", "enum", "const"}),
    "null": frozenset({"type", "description"}),
    "array": frozenset(
        {"type", "description", "items", "minItems", "maxItems"}
    ),
    "object": frozenset(
        {
            "type",
            "description",
            "properties",
            "required",
            "additionalProperties",
        }
    ),
}


def _strict_schema(schema: Any, context: str) -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        raise ValueError(f"{context} schema must be an object")
    schema_type = schema.get("type")
    if not isinstance(schema_type, str) or schema_type not in _TYPE_KEYS:
        raise ValueError(f"{context} has unsupported schema type")
    unsupported = set(schema) - _TYPE_KEYS[schema_type]
    if unsupported:
        raise ValueError(
            f"{context} contains unsupported schema keywords: {sorted(unsupported)}"
        )

    converted = dict(schema)
    if schema_type == "object":
        properties = schema.get("properties")
        if not isinstance(properties, Mapping) or not all(
            isinstance(name, str) for name in properties
        ):
            raise ValueError(f"{context} properties must be an object")
        required = schema.get("required", [])
        if not isinstance(required, list) or set(required) != set(properties):
            raise ValueError(
                f"{context} required fields must exactly match properties"
            )
        if schema.get("additionalProperties") is not False:
            raise ValueError(f"{context} must set additionalProperties to false")
        converted["properties"] = {
            name: _strict_schema(child, f"{context}.{name}")
            for name, child in properties.items()
        }
        if properties:
            converted["required"] = list(required)
        else:
            converted.pop("required", None)
    elif schema_type == "array":
        if "items" not in schema:
            raise ValueError(f"{context} array schema requires items")
        converted["items"] = _strict_schema(schema["items"], f"{context} items")

    return converted


def _content_value(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", by_alias=True, exclude_none=True)
    if hasattr(item, "text"):
        return {"type": getattr(item, "type", "text"), "text": item.text}
    return str(item)
