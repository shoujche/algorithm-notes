"""I/O 密集型：线程在等待 I/O 时会释放 GIL，因此多线程能有效并发。"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor


def io_task(_: int) -> None:
    # 模拟网络/磁盘等待：sleep 期间 GIL 被释放，其他线程可运行
    time.sleep(0.5)


def serial(rounds: int) -> float:
    start = time.perf_counter()
    for i in range(rounds):
        io_task(i)
    return time.perf_counter() - start


def threaded(workers: int, rounds: int) -> float:
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(io_task, range(rounds)))
    return time.perf_counter() - start


if __name__ == "__main__":
    ROUNDS = 8
    print(f"serial:   {serial(ROUNDS):.2f}s")      # ~ 4.0s（8 × 0.5）
    print(f"threaded: {threaded(8, ROUNDS):.2f}s")  # ~ 0.5s（并发等待）
    # 结论：I/O 密集用多线程/协程；CPU 密集才需要多进程。
