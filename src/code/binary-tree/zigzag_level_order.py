from collections import deque

# LeetCode 103. 二叉树的锯齿形层序遍历
# 奇数层从左到右，偶数层从右到左，呈 Z 字形
def zigzagLevelOrder(root):
    if not root:
        return []
    res, q, left_to_right = [], deque([root]), True
    while q:
        level = deque()
        for _ in range(len(q)):
            node = q.popleft()
            # 按当前方向决定加到队首还是队尾，避免最后再整体 reverse
            if left_to_right:
                level.append(node.val)
            else:
                level.appendleft(node.val)
            if node.left:
                q.append(node.left)
            if node.right:
                q.append(node.right)
        res.append(list(level))
        left_to_right = not left_to_right   # 每层翻转方向
    return res
