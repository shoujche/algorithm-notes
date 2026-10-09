def climb_stairs(n: int) -> int:
    """70. 爬楼梯。dp[i] = 爬到第 i 阶的方法数。"""
    if n <= 2:
        return n
    dp = [0] * (n + 1)
    dp[1] = 1
    dp[2] = 2
    for i in range(3, n + 1):
        dp[i] = dp[i - 1] + dp[i - 2]
    return dp[n]


def climb_stairs_rolling(n: int) -> int:
    """同一递推，只留前两格。先看懂上面的表，再看这个。"""
    if n <= 2:
        return n
    prev2, prev1 = 1, 2  # dp[1], dp[2]
    for _ in range(3, n + 1):
        prev2, prev1 = prev1, prev1 + prev2
    return prev1


if __name__ == "__main__":
    assert climb_stairs(1) == 1
    assert climb_stairs(2) == 2
    assert climb_stairs(5) == 8
    assert climb_stairs_rolling(5) == 8
