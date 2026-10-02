# LeetCode 70. 爬楼梯
# 每次可以爬 1 或 2 阶，问到达第 n 阶有多少种不同方法。
# dp[i] = 到达第 i 阶的方法数 = dp[i-1] + dp[i-2]
# 时间 O(n)，空间 O(1)：只保留前两格


def climbStairs(n):
    if n <= 2:
        return n
    one_step_back, two_steps_back = 2, 1  # dp[2], dp[1]
    for _ in range(3, n + 1):
        one_step_back, two_steps_back = one_step_back + two_steps_back, one_step_back
    return one_step_back


if __name__ == "__main__":
    assert climbStairs(1) == 1
    assert climbStairs(2) == 2
    assert climbStairs(5) == 8
