def min_distance(word1: str, word2: str) -> int:
    """72. 编辑距离。dp[i][j] = word1 前 i 个变成 word2 前 j 个的最少操作数。"""
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i  # 删掉 word1 的前 i 个
    for j in range(n + 1):
        dp[0][j] = j  # 插入 word2 的前 j 个
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i - 1] == word2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # 删除 word1[i-1]
                    dp[i][j - 1],      # 插入 word2[j-1]
                    dp[i - 1][j - 1],  # 替换
                )
    return dp[m][n]


if __name__ == "__main__":
    assert min_distance("horse", "ros") == 3
    assert min_distance("intention", "execution") == 5
    assert min_distance("", "a") == 1
