"""竞态条件：即便有 GIL，复合操作(count += 1)也不是原子的，仍需加锁。"""
import threading

count = 0
lock = threading.Lock()


def unsafe_incr(times: int) -> None:
    global count
    for _ in range(times):
        # 读-改-写三步，字节码之间可能被切换 → 丢失更新
        count += 1


def safe_incr(times: int) -> None:
    global count
    for _ in range(times):
        with lock:  # 保证复合操作的原子性
            count += 1


def race(worker, n_threads: int, times: int) -> int:
    global count
    count = 0
    threads = [threading.Thread(target=worker, args=(times,)) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return count


if __name__ == "__main__":
    # GIL 不保证 count += 1 原子，结果常小于期望值
    print("unsafe:", race(unsafe_incr, 8, 100_000))  # < 800000（不确定）
    print("safe:  ", race(safe_incr, 8, 100_000))    # == 800000
