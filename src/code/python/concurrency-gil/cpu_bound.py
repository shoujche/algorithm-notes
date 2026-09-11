"""CPU 密集型：多线程因 GIL 无法并行，多进程才能吃满多核。"""
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


def cpu_task(n: int) -> int:
    # 纯计算，持有 GIL 不释放
    total = 0
    for i in range(n):
        total += i * i
    return total


def run(executor_cls, workers: int, rounds: int, n: int) -> float:
    start = time.perf_counter()
    with executor_cls(max_workers=workers) as ex:
        list(ex.map(cpu_task, [n] * rounds))
    return time.perf_counter() - start


if __name__ == "__main__":
    N, ROUNDS = 5_000_000, 8
    # 多线程：受 GIL 限制，几乎等于串行（甚至更慢，多了切换开销）
    t_thread = run(ThreadPoolExecutor, 4, ROUNDS, N)
    # 多进程：每个进程有独立解释器与 GIL，真正并行
    t_proc = run(ProcessPoolExecutor, 4, ROUNDS, N)
    print(f"threads: {t_thread:.2f}s")   # ~ 串行耗时
    print(f"processes: {t_proc:.2f}s")   # ~ 串行 / 核数
