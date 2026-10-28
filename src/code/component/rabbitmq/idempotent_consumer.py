"""至少一次加上收件箱：同一 message_id 第二次进来只确认，不再改业务数据。"""

from __future__ import annotations

from dataclasses import dataclass, field

from confirm_ack import Broker


@dataclass
class Inbox:
    done: set[str] = field(default_factory=set)
    applied: list[str] = field(default_factory=list)

    def handle(self, message_id: str, body: str) -> str:
        if message_id in self.done:
            return "duplicate"
        self.applied.append(body)
        self.done.add(message_id)
        return "applied"


def consume_once(broker: Broker, inbox: Inbox, prefetch: int) -> str | None:
    delivery = broker.pull(prefetch)
    if delivery is None:
        return None
    try:
        status = inbox.handle(delivery.message_id, delivery.body)
    except Exception:
        # 业务没成功就不要 ack，让代理以后重投。
        broker.crash_consumer()
        raise
    broker.ack(delivery.tag)
    return status


if __name__ == "__main__":
    broker = Broker()
    inbox = Inbox()
    broker.publish("pay-42", "order 42")

    delivery = broker.pull(prefetch=8)
    assert delivery is not None
    assert inbox.handle(delivery.message_id, delivery.body) == "applied"
    # 处理完、确认前进程没了。消息会再来一次。
    broker.crash_consumer()
    assert consume_once(broker, inbox, prefetch=8) == "duplicate"
    assert inbox.applied == ["order 42"]
    assert broker.pull(prefetch=8) is None

    # prefetch 是未确认上限。两条都拉走且不确认时，第三条进不来。
    more = Broker()
    more.publish("a", "1")
    more.publish("b", "2")
    more.publish("c", "3")
    assert more.pull(prefetch=2) is not None
    assert more.pull(prefetch=2) is not None
    assert more.pull(prefetch=2) is None
