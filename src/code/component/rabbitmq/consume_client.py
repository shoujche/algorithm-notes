"""手动确认、限制未确认条数，失败时转入死信，业务侧按 message_id 去重。"""

import os


def open_billing_channel():
    import pika

    connection = pika.BlockingConnection(pika.URLParameters(os.environ["AMQP_URL"]))
    channel = connection.channel()
    channel.exchange_declare(exchange="orders.dlx", exchange_type="fanout", durable=True)
    channel.queue_declare(queue="billing.dead", durable=True)
    channel.queue_bind(queue="billing.dead", exchange="orders.dlx", routing_key="")
    channel.queue_declare(
        queue="billing",
        durable=True,
        arguments={
            # 拒绝且不重新入队时，消息进这个交换机，而不是无限回到原队列。
            "x-dead-letter-exchange": "orders.dlx",
        },
    )
    # 这个消费者手里最多 32 条还没 ack 的消息。1 最均匀也最慢，0 表示不限制。
    channel.basic_qos(prefetch_count=32)
    return connection, channel


def on_message(channel, method, properties, body, inbox: set[str]) -> None:
    message_id = properties.message_id
    if message_id in inbox:
        channel.basic_ack(method.delivery_tag)
        return
    try:
        apply_payment(message_id, body)
    except Exception:
        # requeue=False 让它走死信。requeue=True 会立刻再投给这个消费者。
        channel.basic_nack(method.delivery_tag, requeue=False)
        return
    inbox.add(message_id)
    channel.basic_ack(method.delivery_tag)


def apply_payment(message_id: str, body: bytes) -> None:
    # 生产里把 message_id 的插入和业务写入放进同一个数据库事务。
    del message_id, body


if __name__ == "__main__":
    seen: set[str] = set()

    class Method:
        delivery_tag = 1

    class Properties:
        message_id = "pay-42"

    class Channel:
        def __init__(self) -> None:
            self.acked: list[int] = []

        def basic_ack(self, tag: int) -> None:
            self.acked.append(tag)

        def basic_nack(self, tag: int, requeue: bool) -> None:
            raise AssertionError((tag, requeue))

    channel = Channel()
    on_message(channel, Method(), Properties(), b"{}", seen)
    on_message(channel, Method(), Properties(), b"{}", seen)
    assert seen == {"pay-42"}
    assert channel.acked == [1, 1]
