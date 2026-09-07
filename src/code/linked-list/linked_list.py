class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class LinkedList:
    def __init__(self):
        self.head = None
        self.size = 0

    def add_head(self, val):              # 头部插入 O(1)
        self.head = ListNode(val, self.head)
        self.size += 1

    def add_tail(self, val):              # 尾部插入 O(n)
        node = ListNode(val)
        if not self.head:
            self.head = node
        else:
            cur = self.head
            while cur.next:
                cur = cur.next
            cur.next = node
        self.size += 1

    def insert(self, index, val):         # 在第 index 位插入 O(n)
        if index <= 0:
            return self.add_head(val)
        prev = self.head
        for _ in range(index - 1):
            if prev is None:
                return
            prev = prev.next
        if prev is None:
            return
        prev.next = ListNode(val, prev.next)
        self.size += 1

    def remove(self, val):                # 删除首个等于 val 的节点 O(n)
        dummy = ListNode(0, self.head)    # 哑节点，统一处理头节点
        prev = dummy
        while prev.next:
            if prev.next.val == val:
                prev.next = prev.next.next
                self.size -= 1
                break
            prev = prev.next
        self.head = dummy.next
