"""Literal 把允许的字符串写进类型。运行时要用 get_args 自己校验；Enum 则自带成员。"""

from enum import Enum
from typing import Final, Literal, TypeAlias, get_args

from collections.abc import Callable


Mode: TypeAlias = Literal["read", "write"]
DEFAULT_MODE: Final[Mode] = "read"
Handler: TypeAlias = Callable[[str], str]


def open_note(mode: Mode) -> str:
    if mode == "read":
        return "opened for read"
    return "opened for write"


def require_mode(raw: str) -> Mode:
    # Literal 在运行时只是普通 str，边界上用 get_args 收口。
    allowed = get_args(Mode)
    if raw not in allowed:
        raise ValueError(f"mode must be one of {allowed}")
    return raw  # type: ignore[return-value]


def apply_handler(handler: Handler, text: str) -> str:
    return handler(text)


class ModeEnum(Enum):
    READ = "read"
    WRITE = "write"


def open_with_enum(mode: ModeEnum) -> str:
    return f"opened for {mode.value}"


if __name__ == "__main__":
    assert get_args(Mode) == ("read", "write")
    assert DEFAULT_MODE == "read"
    assert open_note("read") == "opened for read"
    assert require_mode("write") == "write"
    try:
        require_mode("delete")
        raise AssertionError("未知 mode 应被拒绝")
    except ValueError:
        pass
    assert apply_handler(str.upper, "ship") == "SHIP"
    assert open_with_enum(ModeEnum.READ) == "opened for read"
    assert ModeEnum("write") is ModeEnum.WRITE
    assert list(ModeEnum) == [ModeEnum.READ, ModeEnum.WRITE]
