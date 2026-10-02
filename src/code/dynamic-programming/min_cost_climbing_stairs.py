# LeetCode 746. 使用最小花费爬楼梯
# cost[i] 是从第 i 阶向上爬时要付的费用，付完可以再爬 1 或 2 阶。
# 可以从下标 0 或 1 出发，目标是到达楼顶（下标 = len(cost)）。
# dp[i] = 到达下标 i 的最小花费
# dp[i] = min(dp[i-1] + cost[i-1], dp[i-2] + cost[i-2])
# 时间 O(n)，空间 O(1)


def minCostClimbingStairs(cost):
    prev2, prev1 = 0, 0  # 站在 0 或 1 还没付钱
    for i in range(2, len(cost) + 1):
        prev2, prev1 = prev1, min(prev1 + cost[i - 1], prev2 + cost[i - 2])
    return prev1


if __name__ == "__main__":
    assert minCostClimbingStairs([10, 15, 20]) == 15
    assert minCostClimbingStairs([1, 100, 1, 1, 1, 100, 1, 1, 100, 1]) == 6
