def min_cost_climbing_stairs(cost: list[int]) -> int:
    """746. 最小花费爬楼梯。dp[i] = 到达下标 i 的最小花费，楼顶是下标 n。"""
    n = len(cost)
    dp = [0] * (n + 1)  # 从 0 或 1 起步还没付钱，dp[0] = dp[1] = 0
    for i in range(2, n + 1):
        dp[i] = min(dp[i - 1] + cost[i - 1], dp[i - 2] + cost[i - 2])
    return dp[n]


def min_cost_climbing_stairs_rolling(cost: list[int]) -> int:
    """同一递推，只留前两格。"""
    prev2, prev1 = 0, 0
    for i in range(2, len(cost) + 1):
        prev2, prev1 = prev1, min(prev1 + cost[i - 1], prev2 + cost[i - 2])
    return prev1


if __name__ == "__main__":
    assert min_cost_climbing_stairs([10, 15, 20]) == 15
    assert min_cost_climbing_stairs([1, 100, 1, 1, 1, 100, 1, 1, 100, 1]) == 6
    assert min_cost_climbing_stairs_rolling([10, 15, 20]) == 15
