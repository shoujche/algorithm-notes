#include <vector>
#include <queue>
using namespace std;

struct TreeNode {
    int val;
    TreeNode* left;
    TreeNode* right;
    TreeNode(int v) : val(v), left(nullptr), right(nullptr) {}
};

// 前序遍历：根 → 左 → 右
void preorder(TreeNode* node, vector<int>& res) {
    if (!node) return;
    res.push_back(node->val);
    preorder(node->left, res);
    preorder(node->right, res);
}

// 中序遍历：左 → 根 → 右
void inorder(TreeNode* node, vector<int>& res) {
    if (!node) return;
    inorder(node->left, res);
    res.push_back(node->val);
    inorder(node->right, res);
}

// 后序遍历：左 → 右 → 根
void postorder(TreeNode* node, vector<int>& res) {
    if (!node) return;
    postorder(node->left, res);
    postorder(node->right, res);
    res.push_back(node->val);
}

// 层序遍历（BFS）：借助队列，一层一层从左到右
vector<int> levelOrder(TreeNode* root) {
    vector<int> res;
    if (!root) return res;
    queue<TreeNode*> q;
    q.push(root);
    while (!q.empty()) {
        TreeNode* node = q.front();
        q.pop();
        res.push_back(node->val);
        if (node->left) q.push(node->left);
        if (node->right) q.push(node->right);
    }
    return res;
}
