from collections import deque

# LeetCode 199. 二叉树的右视图
# 站在树的右边从上往下看，能看到的节点 = 每一层的最后一个节点
def rightSideView(root):
    if not root:
        return []
    res, q = [], deque([root])
    while q:
        n = len(q)
        for i in range(n):
            node = q.popleft()
            if i == n - 1:              # 该层最后一个 = 最右侧、可见
                res.append(node.val)
            if node.left:
                q.append(node.left)
            if node.right:
                q.append(node.right)
    return res
