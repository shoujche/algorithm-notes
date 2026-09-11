"""手写 LRU 缓存：get / put 均 O(1)。

LRU = Least Recently Used，容量满时淘汰「最久未使用」的条目。
面试要求 get / put 都是 O(1)，所以：
  - 查值要 O(1)      -> 用 dict（哈希表）
  - 维护访问顺序 O(1) -> 用「有序结构」，两种主流写法：
      写法 A：collections.OrderedDict（面试速写首选）
      写法 B：双向链表 + dict（体现底层功底，大厂常要求手写）
"""

from collections import OrderedDict


# ============ 写法 A：OrderedDict（简洁，工程首选）============
class LRUCache:
    """OrderedDict 本身就是「dict + 双向链表」，move_to_end / popitem 都是 O(1)。"""

    def __init__(self, capacity: int):
        self.cap = capacity
        self.od = OrderedDict()  # 队尾 = 最近使用，队首 = 最久未使用

    def get(self, key: int) -> int:
        if key not in self.od:
            return -1
        self.od.move_to_end(key)  # 命中即刷新为「最近使用」
        return self.od[key]

    def put(self, key: int, value: int) -> None:
        if key in self.od:
            self.od.move_to_end(key)  # 已存在：更新并刷新顺序
        self.od[key] = value
        if len(self.od) > self.cap:
            self.od.popitem(last=False)  # last=False 弹出队首（最久未使用）


# ============ 写法 B：双向链表 + dict（手写底层）============
class Node:
    """双向链表节点，同时存 key（淘汰时要用 key 回删 dict）。"""

    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key=0, val=0):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class LRUCacheLinkedList:
    """dict 存 key->Node 做 O(1) 定位；双向链表维护访问顺序。

    用 head / tail 两个哨兵节点，省去大量边界判断（空链表、头尾操作）。
    约定：head 侧 = 最近使用，tail 侧 = 最久未使用。
    """

    def __init__(self, capacity: int):
        self.cap = capacity
        self.map = {}  # key -> Node
        self.head = Node()  # 哨兵头
        self.tail = Node()  # 哨兵尾
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: Node) -> None:
        """从链表摘除节点，O(1)。"""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_front(self, node: Node) -> None:
        """插到 head 之后，标记为最近使用，O(1)。"""
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key not in self.map:
            return -1
        node = self.map[key]
        self._remove(node)  # 命中：摘下再插到头部（刷新为最近使用）
        self._add_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        if key in self.map:
            self._remove(self.map[key])  # 已存在：先摘除旧节点
        node = Node(key, value)
        self.map[key] = node
        self._add_front(node)
        if len(self.map) > self.cap:
            lru = self.tail.prev  # tail 前一个 = 最久未使用
            self._remove(lru)
            del self.map[lru.key]  # 别忘了同步删 dict


if __name__ == "__main__":
    for Impl in (LRUCache, LRUCacheLinkedList):
        c = Impl(2)
        c.put(1, 1)
        c.put(2, 2)
        assert c.get(1) == 1  # 访问 1，使 2 变成最久未使用
        c.put(3, 3)  # 容量满，淘汰 2
        assert c.get(2) == -1
        c.put(4, 4)  # 淘汰 1
        assert c.get(1) == -1
        assert c.get(3) == 3 and c.get(4) == 4
        print(f"{Impl.__name__} 通过 ✓")
