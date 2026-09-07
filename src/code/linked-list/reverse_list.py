def reverseList(head: ListNode) -> ListNode:
    prev = None
    curr = head
    while curr:
        nxt = curr.next     # 1. 记住下一个节点
        curr.next = prev    # 2. 当前节点掉头指向前面
        prev = curr         # 3. prev 前移
        curr = nxt          # 4. curr 前移
    return prev             # prev 是新的头节点
