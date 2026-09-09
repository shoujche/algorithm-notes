import java.util.*;

class TreeNode {
    int val;
    TreeNode left, right;
    TreeNode(int val) { this.val = val; }
}

class Traversal {
    // 前序遍历：根 → 左 → 右
    List<Integer> preorder(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        dfsPre(root, res);
        return res;
    }
    void dfsPre(TreeNode node, List<Integer> res) {
        if (node == null) return;
        res.add(node.val);
        dfsPre(node.left, res);
        dfsPre(node.right, res);
    }

    // 中序遍历：左 → 根 → 右
    List<Integer> inorder(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        dfsIn(root, res);
        return res;
    }
    void dfsIn(TreeNode node, List<Integer> res) {
        if (node == null) return;
        dfsIn(node.left, res);
        res.add(node.val);
        dfsIn(node.right, res);
    }

    // 后序遍历：左 → 右 → 根
    List<Integer> postorder(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        dfsPost(root, res);
        return res;
    }
    void dfsPost(TreeNode node, List<Integer> res) {
        if (node == null) return;
        dfsPost(node.left, res);
        dfsPost(node.right, res);
        res.add(node.val);
    }

    // 层序遍历（BFS）：借助队列，一层一层从左到右
    List<Integer> levelOrder(TreeNode root) {
        List<Integer> res = new ArrayList<>();
        if (root == null) return res;
        Queue<TreeNode> q = new LinkedList<>();
        q.offer(root);
        while (!q.isEmpty()) {
            TreeNode node = q.poll();
            res.add(node.val);
            if (node.left != null) q.offer(node.left);
            if (node.right != null) q.offer(node.right);
        }
        return res;
    }
}
