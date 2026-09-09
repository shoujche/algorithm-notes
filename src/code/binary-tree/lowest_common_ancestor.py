# LeetCode 236. 二叉树的最近公共祖先
# 后序递归：在以 root 为根的子树里，找 p、q 的最近公共祖先
def lowestCommonAncestor(root, p, q):
    if root is None or root is p or root is q:
        return root                      # 命中目标节点或走到空，直接返回
    left = lowestCommonAncestor(root.left, p, q)
    right = lowestCommonAncestor(root.right, p, q)
    if left and right:                   # p、q 分别落在左右两侧 → 当前节点就是 LCA
        return root
    return left if left else right       # 都在同一侧，返回非空的那一侧
