from collections import deque

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left            # 左子节点
        self.right = right          # 右子节点

# 前序遍历：根 → 左 → 右
def preorder(root):
    if not root:
        return []
    return [root.val] + preorder(root.left) + preorder(root.right)

# 中序遍历：左 → 根 → 右（二叉搜索树的中序结果是有序的）
def inorder(root):
    if not root:
        return []
    return inorder(root.left) + [root.val] + inorder(root.right)

# 后序遍历：左 → 右 → 根
def postorder(root):
    if not root:
        return []
    return postorder(root.left) + postorder(root.right) + [root.val]

# 层序遍历（BFS）：借助队列，一层一层从左到右
def level_order(root):
    if not root:
        return []
    res, q = [], deque([root])
    while q:
        node = q.popleft()
        res.append(node.val)
        if node.left:
            q.append(node.left)
        if node.right:
            q.append(node.right)
    return res
