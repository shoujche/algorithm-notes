from collections import deque

# LeetCode 958. 二叉树的完全性检验
# 完全二叉树：层序遍历时，一旦遇到空节点，其后不能再出现任何非空节点
def isCompleteTree(root):
    q = deque([root])
    seen_none = False
    while q:
        node = q.popleft()
        if node is None:
            seen_none = True             # 记录：已经出现过空位
        else:
            if seen_none:                # 空位之后又冒出真实节点 → 不是完全二叉树
                return False
            q.append(node.left)          # 关键：空孩子也入队，用来暴露“空洞”
            q.append(node.right)
    return True
