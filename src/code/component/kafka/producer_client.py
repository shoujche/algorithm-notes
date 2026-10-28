"""高吞吐生产者的配置。键名就是 broker 认识的 producer 配置。

阅读用。真正发送需要 pip install confluent-kafka，以及环境变量 KAFKA_BOOTSTRAP。
不要把账号写进代码。
"""

import os


def producer_config(bootstrap: str) -> dict[str, str | int | bool]:
    return {
        "bootstrap.servers": bootstrap,
        # all：等 ISR 里的每个副本都写入。1 只等 leader。0 发出去就返回。
        "acks": "all",
        # 凑满一批或等满这段时间再发。单条发送把吞吐耗在往返上。
        "linger.ms": 20,
        "batch.size": 64 * 1024,
        # 压缩打在一批上。单条几乎省不下字节。
        "compression.type": "lz4",
        # 幂等：同一分区里，重试不会把同一条再写一份。它要求 acks=all。
        "enable.idempotence": True,
        "max.in.flight.requests.per.connection": 5,
        "retries": 10,
    }


def send_order(order_id: str, body: str) -> None:
    from confluent_kafka import Producer

    producer = Producer(producer_config(os.environ["KAFKA_BOOTSTRAP"]))

    def on_delivery(err, msg) -> None:
        if err is not None:
            raise RuntimeError(err)

    producer.produce(
        "orders",
        key=order_id.encode(),
        value=body.encode(),
        on_delivery=on_delivery,
    )
    # poll 把回调交出来。flush 等到这批确认，或超时。
    producer.flush(timeout=10)


if __name__ == "__main__":
    config = producer_config("localhost:9092")
    assert config["acks"] == "all"
    assert config["enable.idempotence"] is True
    assert config["linger.ms"] == 20
