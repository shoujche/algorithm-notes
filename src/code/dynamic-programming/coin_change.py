def coin_change(coins: list[int], amount: int) -> int:
    """322. 零钱兑换。dp[x] = 凑出金额 x 的最少硬币数，凑不出先记成 amount+1。"""
    impossible = amount + 1
    dp = [impossible] * (amount + 1)
    dp[0] = 0
    for x in range(1, amount + 1):
        for coin in coins:
            if coin <= x:
                dp[x] = min(dp[x], dp[x - coin] + 1)
    return dp[amount] if dp[amount] != impossible else -1


if __name__ == "__main__":
    assert coin_change([1, 2, 5], 11) == 3
    assert coin_change([2], 3) == -1
    assert coin_change([1], 0) == 0
