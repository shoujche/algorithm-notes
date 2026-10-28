"""发布确认发生在入队之后。消费者处理成功再 ack；没 ack 就离开，消息会带 redelivered 回来。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Delivery:
    message_id: str
    body: str
    tag: int
    persistent: bool
    redelivered: bool = False


@dataclass
class Queue:
    ready: list[Delivery] = field(default_factory=list)
    unacked: dict[int, Delivery] = field(default_factory=dict)
    disk: list[str] = field(default_factory=list)
    next_tag: int = 1

    def enqueue(self, message_id: str, body: str, persistent: bool) -> Delivery:
        delivery = Delivery(message_id, body, self.next_tag, persistent)
        self.next_tag += 1
        self.ready.append(delivery)
        if persistent:
            self.disk.append(message_id)
        return delivery


@dataclass
class Broker:
    queue: Queue = field(default_factory=Queue)
    confirms: list[str] = field(default_factory=list)

    def publish(self, message_id: str, body: str, persistent: bool = True) -> str:
        delivery = self.queue.enqueue(message_id, body, persistent)
        # confirm 表示代理已经接手。持久化消息要等写入 disk 之后才确认。
        if persistent and message_id not in self.queue.disk:
            raise RuntimeError("persistent message was not stored")
        self.confirms.append(message_id)
        return delivery.message_id

    def pull(self, prefetch: int) -> Delivery | None:
        if len(self.queue.unacked) >= prefetch:
            return None
        if not self.queue.ready:
            return None
        delivery = self.queue.ready.pop(0)
        self.queue.unacked[delivery.tag] = delivery
        return delivery

    def ack(self, tag: int) -> None:
        self.queue.unacked.pop(tag)

    def crash_consumer(self) -> None:
        # 未确认的消息回到队头，并标成重新投递。
        returned = list(self.queue.unacked.values())
        self.queue.unacked.clear()
        for delivery in reversed(returned):
            delivery.redelivered = True
            self.queue.ready.insert(0, delivery)


if __name__ == "__main__":
    broker = Broker()
    assert broker.publish("m1", "paid") == "m1"
    assert broker.confirms == ["m1"]
    assert broker.queue.disk == ["m1"]

    first = broker.pull(prefetch=1)
    assert first is not None and first.body == "paid"
    assert broker.pull(prefetch=1) is None
    broker.crash_consumer()
    again = broker.pull(prefetch=1)
    assert again is not None
    assert again.redelivered is True
    assert again.message_id == "m1"
    broker.ack(again.tag)
    assert broker.pull(prefetch=1) is None
