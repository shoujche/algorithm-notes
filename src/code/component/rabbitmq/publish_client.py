"""连接上开通道，声明交换机和队列，持久化之后等待发布确认。

阅读用。真正发布需要 pip install pika，以及环境变量 AMQP_URL。
AMQP_URL 形如 amqp://localhost:5672/。密码放在环境变量里。
"""

import os


def publish_paid(order_id: str, body: bytes) -> None:
    import pika

    params = pika.URLParameters(os.environ["AMQP_URL"])
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    # 一条连接上可以开很多通道。通道不是线程安全的，一个线程用一个通道。
    channel.exchange_declare(exchange="orders", exchange_type="topic", durable=True)
    channel.queue_declare(queue="billing", durable=True)
    channel.queue_bind(queue="billing", exchange="orders", routing_key="order.paid")
    channel.confirm_delivery()
    channel.basic_publish(
        exchange="orders",
        routing_key="order.paid",
        body=body,
        mandatory=True,
        properties=pika.BasicProperties(
            # 2 表示持久化。队列 durable 和消息持久化要同时有，重启才还在。
            delivery_mode=2,
            message_id=order_id,
            content_type="application/json",
        ),
    )
    connection.close()


if __name__ == "__main__":
    assert os.environ.get("AMQP_URL", "amqp://localhost:5672/").startswith("amqp://")
