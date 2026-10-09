def max_sub_array(nums: list[int]) -> int:
    """53. 最大子数组和。dp[i] = 以 nums[i] 结尾的最大和。答案是 dp 里的最大值。"""
    dp = [0] * len(nums)
    dp[0] = nums[0]
    best = dp[0]
    for i in range(1, len(nums)):
        dp[i] = max(nums[i], dp[i - 1] + nums[i])
        best = max(best, dp[i])
    return best


def max_sub_array_rolling(nums: list[int]) -> int:
    """同一递推，只留「以当前位置结尾」的那一格。"""
    best = current = nums[0]
    for value in nums[1:]:
        current = max(value, current + value)
        best = max(best, current)
    return best


if __name__ == "__main__":
    sample = [-2, 1, -3, 4, -1, 2, 1, -5, 4]
    assert max_sub_array(sample) == 6
    assert max_sub_array_rolling(sample) == 6
    assert max_sub_array([1]) == 1
    assert max_sub_array([-2, -1]) == -1
