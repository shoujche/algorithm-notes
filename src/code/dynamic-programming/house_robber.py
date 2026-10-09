def rob(nums: list[int]) -> int:
    """198. 打家劫舍。dp[i] = 考虑前 i 间房时的最大金额。"""
    n = len(nums)
    dp = [0] * (n + 1)  # dp[0] = 0，还没看任何房子
    for i in range(1, n + 1):
        skip = dp[i - 1]
        take = nums[i - 1] + (dp[i - 2] if i >= 2 else 0)
        dp[i] = max(skip, take)
    return dp[n]


def rob_rolling(nums: list[int]) -> int:
    """同一递推，只留前两格。"""
    prev2, prev1 = 0, 0
    for value in nums:
        prev2, prev1 = prev1, max(prev1, prev2 + value)
    return prev1


if __name__ == "__main__":
    assert rob([1, 2, 3, 1]) == 4
    assert rob([2, 7, 9, 3, 1]) == 12
    assert rob_rolling([2, 7, 9, 3, 1]) == 12
