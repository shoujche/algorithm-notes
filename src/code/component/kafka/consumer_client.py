"""一个消费者线程只 poll 自己。处理成功再提交这条消息的位点。

阅读用。真正消费需要 pip install confluent-kafka，以及环境变量 KAFKA_BOOTSTRAP。
"""

import os


def consumer_config(bootstrap: str, group_id: str) -> dict[str, str | int | bool]:
    return {
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        # 关掉自动提交。自动提交可能发生在处理完之前，崩溃后这条就不再投递。
        "enable.auto.commit": False,
        # 组里还没有位点时，从最早的消息读。生产上按业务选 earliest 或 latest。
        "auto.offset.reset": "earliest",
        # 这一轮处理必须在这个时间内 poll 下一次，否则成员被看成已离开，分区划给别人。
        "max.poll.interval.ms": 300_000,
        # 一次拉取尽量攒够这些字节，到 fetch.max.wait.ms 也会返回。
        "fetch.min.bytes": 1024,
    }


def consume_orders(handle) -> None:
    from confluent_kafka import Consumer

    consumer = Consumer(consumer_config(os.environ["KAFKA_BOOTSTRAP"], "billing"))
    consumer.subscribe(["orders"])
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None or msg.error():
                continue
            handle(msg.key(), msg.value())
            # 提交的是这一条。同一分区并发处理时，只能提交连续完成的位点。
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()


if __name__ == "__main__":
    config = consumer_config("localhost:9092", "billing")
    assert config["enable.auto.commit"] is False
    assert config["group.id"] == "billing"
