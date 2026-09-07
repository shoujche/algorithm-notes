package linkedlist

type ListNode struct {
	Val  int
	Next *ListNode
}

type LinkedList struct {
	Head *ListNode
	Size int
}

func (l *LinkedList) AddHead(val int) { // 头部插入 O(1)
	l.Head = &ListNode{Val: val, Next: l.Head}
	l.Size++
}

func (l *LinkedList) AddTail(val int) { // 尾部插入 O(n)
	node := &ListNode{Val: val}
	if l.Head == nil {
		l.Head = node
	} else {
		cur := l.Head
		for cur.Next != nil {
			cur = cur.Next
		}
		cur.Next = node
	}
	l.Size++
}

func (l *LinkedList) Insert(index, val int) { // 在第 index 位插入 O(n)
	if index <= 0 {
		l.AddHead(val)
		return
	}
	prev := l.Head
	for i := 0; i < index-1 && prev != nil; i++ {
		prev = prev.Next
	}
	if prev == nil {
		return
	}
	prev.Next = &ListNode{Val: val, Next: prev.Next}
	l.Size++
}

func (l *LinkedList) Remove(val int) { // 删除首个等于 val 的节点 O(n)
	dummy := &ListNode{Next: l.Head} // 哑节点，统一处理头节点
	prev := dummy
	for prev.Next != nil {
		if prev.Next.Val == val {
			prev.Next = prev.Next.Next
			l.Size--
			break
		}
		prev = prev.Next
	}
	l.Head = dummy.Next
}
