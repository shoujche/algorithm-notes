"""dataclass 生成初始化、比较和替换。frozen 的值对象改字段会得到新实例；列表字段用 default_factory。"""

from dataclasses import asdict, dataclass, field, replace
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class Note:
    title: str
    tags: tuple[str, ...] = ()
    kind: ClassVar[str] = "note"

    def renamed(self, title: str) -> "Note":
        return replace(self, title=title)


@dataclass
class Draft:
    title: str
    lines: list[str] = field(default_factory=list)

    def add(self, line: str) -> None:
        self.lines.append(line)


if __name__ == "__main__":
    note = Note("plan", ("draft",))
    renamed = note.renamed("ship")
    assert note.title == "plan"
    assert renamed.title == "ship"
    assert renamed.tags == ("draft",)
    assert note == Note("plan", ("draft",))
    assert asdict(note) == {"title": "plan", "tags": ("draft",)}
    assert "kind" not in asdict(note)
    try:
        note.title = "x"  # type: ignore[misc]
        raise AssertionError("frozen 实例应拒绝赋值")
    except AttributeError:
        pass

    first = Draft("a")
    second = Draft("b")
    first.add("one")
    assert first.lines == ["one"]
    assert second.lines == []
