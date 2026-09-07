class DListNode:
    def __init__(self, val=0):
        self.val = val
        self.prev = None
        self.next = None

class DoublyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self.size = 0

    def add_head(self, val):              # 头部插入 O(1)
        node = DListNode(val)
        if not self.head:
            self.head = self.tail = node
        else:
            node.next = self.head
            self.head.prev = node
            self.head = node
        self.size += 1

    def add_tail(self, val):              # 尾部插入 O(1)
        node = DListNode(val)
        if not self.tail:
            self.head = self.tail = node
        else:
            node.prev = self.tail
            self.tail.next = node
            self.tail = node
        self.size += 1

    def insert(self, index, val):         # 在第 index 位插入 O(n)
        if index <= 0:
            return self.add_head(val)
        if index >= self.size:
            return self.add_tail(val)
        cur = self.head
        for _ in range(index):
            cur = cur.next
        node = DListNode(val)             # 插到 cur 之前
        node.prev = cur.prev
        node.next = cur
        cur.prev.next = node
        cur.prev = node
        self.size += 1

    def remove(self, val):                # 删除首个等于 val 的节点 O(n)
        cur = self.head
        while cur:
            if cur.val == val:
                if cur.prev:
                    cur.prev.next = cur.next
                else:
                    self.head = cur.next
                if cur.next:
                    cur.next.prev = cur.prev
                else:
                    self.tail = cur.prev
                self.size -= 1
                break
            cur = cur.next
