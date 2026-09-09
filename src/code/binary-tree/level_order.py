from collections import deque

# LeetCode 102. 二叉树的层序遍历
# 按层返回：[[第一层], [第二层], ...]
def levelOrder(root):
    if not root:
        return []
    res, q = [], deque([root])
    while q:
        level = []
        for _ in range(len(q)):         # 固定住「当前这一层」的节点数
            node = q.popleft()
            level.append(node.val)
            if node.left:
                q.append(node.left)
            if node.right:
                q.append(node.right)
        res.append(level)
    return res
