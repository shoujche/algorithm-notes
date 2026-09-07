package linkedlist

type DListNode struct {
	Val        int
	Prev, Next *DListNode
}

type DoublyLinkedList struct {
	Head, Tail *DListNode
	Size       int
}

func (l *DoublyLinkedList) AddHead(val int) { // 头部插入 O(1)
	node := &DListNode{Val: val}
	if l.Head == nil {
		l.Head, l.Tail = node, node
	} else {
		node.Next = l.Head
		l.Head.Prev = node
		l.Head = node
	}
	l.Size++
}

func (l *DoublyLinkedList) AddTail(val int) { // 尾部插入 O(1)
	node := &DListNode{Val: val}
	if l.Tail == nil {
		l.Head, l.Tail = node, node
	} else {
		node.Prev = l.Tail
		l.Tail.Next = node
		l.Tail = node
	}
	l.Size++
}

func (l *DoublyLinkedList) Insert(index, val int) { // 在第 index 位插入 O(n)
	if index <= 0 {
		l.AddHead(val)
		return
	}
	if index >= l.Size {
		l.AddTail(val)
		return
	}
	cur := l.Head
	for i := 0; i < index; i++ {
		cur = cur.Next
	}
	node := &DListNode{Val: val, Prev: cur.Prev, Next: cur}
	cur.Prev.Next = node
	cur.Prev = node
	l.Size++
}

func (l *DoublyLinkedList) Remove(val int) { // 删除首个等于 val 的节点 O(n)
	cur := l.Head
	for cur != nil {
		if cur.Val == val {
			if cur.Prev != nil {
				cur.Prev.Next = cur.Next
			} else {
				l.Head = cur.Next
			}
			if cur.Next != nil {
				cur.Next.Prev = cur.Prev
			} else {
				l.Tail = cur.Prev
			}
			l.Size--
			break
		}
		cur = cur.Next
	}
}
