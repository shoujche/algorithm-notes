# LeetCode 198. 打家劫舍
# 一排房屋，相邻两间不能在同一晚偷。求能偷到的最高金额。
# dp[i] = 考虑前 i 间房时的最大金额
# dp[i] = max(不偷这间 dp[i-1], 偷这间 dp[i-2] + nums[i-1])
# 时间 O(n)，空间 O(1)


def rob(nums):
    prev2, prev1 = 0, 0  # dp[i-2], dp[i-1]，一开始还没看任何房子
    for value in nums:
        prev2, prev1 = prev1, max(prev1, prev2 + value)
    return prev1


if __name__ == "__main__":
    assert rob([1, 2, 3, 1]) == 4
    assert rob([2, 7, 9, 3, 1]) == 12
