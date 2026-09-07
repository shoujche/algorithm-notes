class LRUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.cache = {}                 # key -> node（哈希表 O(1) 查找）
        self.head = DListNode()         # 哨兵头（头部 = 最近使用）
        self.tail = DListNode()         # 哨兵尾（尾部 = 最久未使用）
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node):            # O(1) 摘除
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_front(self, node):         # O(1) 插到头部
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        node = self.cache[key]
        self._remove(node)              # 移到头部 = 标记为最近使用
        self._add_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self._remove(self.cache[key])
        node = DListNode(value); node.key = key
        self.cache[key] = node
        self._add_front(node)
        if len(self.cache) > self.cap:          # 超容量
            lru = self.tail.prev                 # 淘汰尾部
            self._remove(lru)
            del self.cache[lru.key]
