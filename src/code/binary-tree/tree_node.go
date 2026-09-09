package binarytree

type TreeNode struct {
	Val   int
	Left  *TreeNode
	Right *TreeNode
}

// 前序遍历：根 → 左 → 右
func Preorder(root *TreeNode) []int {
	if root == nil {
		return nil
	}
	res := []int{root.Val}
	res = append(res, Preorder(root.Left)...)
	res = append(res, Preorder(root.Right)...)
	return res
}

// 中序遍历：左 → 根 → 右
func Inorder(root *TreeNode) []int {
	if root == nil {
		return nil
	}
	res := Inorder(root.Left)
	res = append(res, root.Val)
	res = append(res, Inorder(root.Right)...)
	return res
}

// 后序遍历：左 → 右 → 根
func Postorder(root *TreeNode) []int {
	if root == nil {
		return nil
	}
	res := Postorder(root.Left)
	res = append(res, Postorder(root.Right)...)
	res = append(res, root.Val)
	return res
}

// 层序遍历（BFS）：借助队列，一层一层从左到右
func LevelOrder(root *TreeNode) []int {
	if root == nil {
		return nil
	}
	res := []int{}
	queue := []*TreeNode{root}
	for len(queue) > 0 {
		node := queue[0]
		queue = queue[1:]
		res = append(res, node.Val)
		if node.Left != nil {
			queue = append(queue, node.Left)
		}
		if node.Right != nil {
			queue = append(queue, node.Right)
		}
	}
	return res
}
