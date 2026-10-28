"""direct 按完整键投递，topic 用 * 和 #，fanout 忽略键、交给每个绑定。"""

from __future__ import annotations

from dataclasses import dataclass, field


def topic_match(pattern: str, key: str) -> bool:
    """* 恰好一个词，# 零个或多个词。词用点分开。"""

    def walk(pat: list[str], words: list[str]) -> bool:
        if not pat:
            return not words
        if pat[0] == "#":
            if len(pat) == 1:
                return True
            return any(walk(pat[1:], words[take:]) for take in range(len(words) + 1))
        if not words:
            return False
        if pat[0] in {"*", words[0]}:
            return walk(pat[1:], words[1:])
        return False

    return walk(pattern.split("."), key.split("."))


@dataclass
class Queue:
    name: str
    messages: list[str] = field(default_factory=list)


@dataclass
class Exchange:
    kind: str
    bindings: list[tuple[str, Queue]] = field(default_factory=list)

    def bind(self, queue: Queue, pattern: str) -> None:
        self.bindings.append((pattern, queue))

    def publish(self, routing_key: str, body: str) -> list[str]:
        delivered: list[str] = []
        seen: set[str] = set()
        for pattern, queue in self.bindings:
            matched = (
                self.kind == "fanout"
                or (self.kind == "direct" and pattern == routing_key)
                or (self.kind == "topic" and topic_match(pattern, routing_key))
            )
            if matched and queue.name not in seen:
                queue.messages.append(body)
                delivered.append(queue.name)
                seen.add(queue.name)
        return delivered


if __name__ == "__main__":
    assert topic_match("order.*", "order.created") is True
    assert topic_match("order.*", "order.created.eu") is False
    assert topic_match("order.#", "order") is True
    assert topic_match("order.#", "order.created.eu") is True

    billing = Queue("billing")
    audit = Queue("audit")
    direct = Exchange("direct")
    direct.bind(billing, "order.paid")
    direct.bind(audit, "order.created")
    assert direct.publish("order.paid", "42") == ["billing"]
    assert audit.messages == []

    created = Queue("created")
    everything = Queue("everything")
    topic = Exchange("topic")
    topic.bind(created, "order.*")
    topic.bind(everything, "order.#")
    assert topic.publish("order.created", "a") == ["created", "everything"]
    assert topic.publish("order.created.eu", "b") == ["everything"]

    fan_a, fan_b = Queue("a"), Queue("b")
    fanout = Exchange("fanout")
    fanout.bind(fan_a, "")
    fanout.bind(fan_b, "")
    assert fanout.publish("ignored", "hi") == ["a", "b"]
