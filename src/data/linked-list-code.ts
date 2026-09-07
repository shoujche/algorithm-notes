// 链表代码：单向 / 双向，各含 add_head / add_tail / insert / remove
// 每个结构提供 Python / Java / Go / C++ 四种语言实现，Python 为默认第一项。

export interface CodeVariant {
  lang: string;   // Shiki 高亮语言
  label: string;  // 选项卡显示名
  file: string;   // 文件名（右侧显示）
  code: string;
}

/* ============================ 单向链表 ============================ */

const singlyPy = `class ListNode:
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
        self.head = dummy.next`;

const singlyJava = `class ListNode {
    int val;
    ListNode next;
    ListNode(int val) { this.val = val; }
}

class LinkedList {
    ListNode head;
    int size;

    void addHead(int val) {                 // 头部插入 O(1)
        ListNode node = new ListNode(val);
        node.next = head;
        head = node;
        size++;
    }

    void addTail(int val) {                 // 尾部插入 O(n)
        ListNode node = new ListNode(val);
        if (head == null) {
            head = node;
        } else {
            ListNode cur = head;
            while (cur.next != null) cur = cur.next;
            cur.next = node;
        }
        size++;
    }

    void insert(int index, int val) {       // 在第 index 位插入 O(n)
        if (index <= 0) { addHead(val); return; }
        ListNode prev = head;
        for (int i = 0; i < index - 1 && prev != null; i++) prev = prev.next;
        if (prev == null) return;
        ListNode node = new ListNode(val);
        node.next = prev.next;
        prev.next = node;
        size++;
    }

    void remove(int val) {                  // 删除首个等于 val 的节点 O(n)
        ListNode dummy = new ListNode(0);   // 哑节点，统一处理头节点
        dummy.next = head;
        ListNode prev = dummy;
        while (prev.next != null) {
            if (prev.next.val == val) {
                prev.next = prev.next.next;
                size--;
                break;
            }
            prev = prev.next;
        }
        head = dummy.next;
    }
}`;

const singlyGo = `type ListNode struct {
    Val  int
    Next *ListNode
}

type LinkedList struct {
    Head *ListNode
    Size int
}

func (l *LinkedList) AddHead(val int) {          // 头部插入 O(1)
    l.Head = &ListNode{Val: val, Next: l.Head}
    l.Size++
}

func (l *LinkedList) AddTail(val int) {          // 尾部插入 O(n)
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

func (l *LinkedList) Insert(index, val int) {    // 在第 index 位插入 O(n)
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

func (l *LinkedList) Remove(val int) {           // 删除首个等于 val 的节点 O(n)
    dummy := &ListNode{Next: l.Head}             // 哑节点，统一处理头节点
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
}`;

const singlyCpp = `struct ListNode {
    int val;
    ListNode* next;
    ListNode(int v) : val(v), next(nullptr) {}
};

class LinkedList {
public:
    ListNode* head = nullptr;
    int size = 0;

    void addHead(int val) {                 // 头部插入 O(1)
        ListNode* node = new ListNode(val);
        node->next = head;
        head = node;
        ++size;
    }

    void addTail(int val) {                 // 尾部插入 O(n)
        ListNode* node = new ListNode(val);
        if (!head) {
            head = node;
        } else {
            ListNode* cur = head;
            while (cur->next) cur = cur->next;
            cur->next = node;
        }
        ++size;
    }

    void insert(int index, int val) {       // 在第 index 位插入 O(n)
        if (index <= 0) { addHead(val); return; }
        ListNode* prev = head;
        for (int i = 0; i < index - 1 && prev; ++i) prev = prev->next;
        if (!prev) return;
        ListNode* node = new ListNode(val);
        node->next = prev->next;
        prev->next = node;
        ++size;
    }

    void remove(int val) {                  // 删除首个等于 val 的节点 O(n)
        ListNode dummy(0);                  // 哑节点，统一处理头节点
        dummy.next = head;
        ListNode* prev = &dummy;
        while (prev->next) {
            if (prev->next->val == val) {
                ListNode* del = prev->next;
                prev->next = del->next;
                delete del;                 // 释放内存
                --size;
                break;
            }
            prev = prev->next;
        }
        head = dummy.next;
    }
};`;

export const singlyVariants: CodeVariant[] = [
  { lang: 'python', label: 'Python', file: 'linked_list.py', code: singlyPy },
  { lang: 'java', label: 'Java', file: 'LinkedList.java', code: singlyJava },
  { lang: 'go', label: 'Go', file: 'linked_list.go', code: singlyGo },
  { lang: 'cpp', label: 'C++', file: 'linked_list.cpp', code: singlyCpp },
];

/* ============================ 双向链表 ============================ */

const doublyPy = `class DListNode:
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
            cur = cur.next`;

const doublyJava = `class DListNode {
    int val;
    DListNode prev, next;
    DListNode(int val) { this.val = val; }
}

class DoublyLinkedList {
    DListNode head, tail;
    int size;

    void addHead(int val) {                 // 头部插入 O(1)
        DListNode node = new DListNode(val);
        if (head == null) {
            head = tail = node;
        } else {
            node.next = head;
            head.prev = node;
            head = node;
        }
        size++;
    }

    void addTail(int val) {                 // 尾部插入 O(1)
        DListNode node = new DListNode(val);
        if (tail == null) {
            head = tail = node;
        } else {
            node.prev = tail;
            tail.next = node;
            tail = node;
        }
        size++;
    }

    void insert(int index, int val) {       // 在第 index 位插入 O(n)
        if (index <= 0) { addHead(val); return; }
        if (index >= size) { addTail(val); return; }
        DListNode cur = head;
        for (int i = 0; i < index; i++) cur = cur.next;
        DListNode node = new DListNode(val);
        node.prev = cur.prev;
        node.next = cur;
        cur.prev.next = node;
        cur.prev = node;
        size++;
    }

    void remove(int val) {                  // 删除首个等于 val 的节点 O(n)
        DListNode cur = head;
        while (cur != null) {
            if (cur.val == val) {
                if (cur.prev != null) cur.prev.next = cur.next;
                else head = cur.next;
                if (cur.next != null) cur.next.prev = cur.prev;
                else tail = cur.prev;
                size--;
                break;
            }
            cur = cur.next;
        }
    }
}`;

const doublyGo = `type DListNode struct {
    Val        int
    Prev, Next *DListNode
}

type DoublyLinkedList struct {
    Head, Tail *DListNode
    Size       int
}

func (l *DoublyLinkedList) AddHead(val int) {        // 头部插入 O(1)
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

func (l *DoublyLinkedList) AddTail(val int) {        // 尾部插入 O(1)
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

func (l *DoublyLinkedList) Insert(index, val int) {  // 在第 index 位插入 O(n)
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

func (l *DoublyLinkedList) Remove(val int) {         // 删除首个等于 val 的节点 O(n)
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
}`;

const doublyCpp = `struct DListNode {
    int val;
    DListNode *prev, *next;
    DListNode(int v) : val(v), prev(nullptr), next(nullptr) {}
};

class DoublyLinkedList {
public:
    DListNode *head = nullptr, *tail = nullptr;
    int size = 0;

    void addHead(int val) {                 // 头部插入 O(1)
        DListNode* node = new DListNode(val);
        if (!head) {
            head = tail = node;
        } else {
            node->next = head;
            head->prev = node;
            head = node;
        }
        ++size;
    }

    void addTail(int val) {                 // 尾部插入 O(1)
        DListNode* node = new DListNode(val);
        if (!tail) {
            head = tail = node;
        } else {
            node->prev = tail;
            tail->next = node;
            tail = node;
        }
        ++size;
    }

    void insert(int index, int val) {       // 在第 index 位插入 O(n)
        if (index <= 0) { addHead(val); return; }
        if (index >= size) { addTail(val); return; }
        DListNode* cur = head;
        for (int i = 0; i < index; ++i) cur = cur->next;
        DListNode* node = new DListNode(val);
        node->prev = cur->prev;
        node->next = cur;
        cur->prev->next = node;
        cur->prev = node;
        ++size;
    }

    void remove(int val) {                  // 删除首个等于 val 的节点 O(n)
        DListNode* cur = head;
        while (cur) {
            if (cur->val == val) {
                if (cur->prev) cur->prev->next = cur->next;
                else head = cur->next;
                if (cur->next) cur->next->prev = cur->prev;
                else tail = cur->prev;
                delete cur;                 // 释放内存
                --size;
                break;
            }
            cur = cur->next;
        }
    }
};`;

export const doublyVariants: CodeVariant[] = [
  { lang: 'python', label: 'Python', file: 'doubly_linked_list.py', code: doublyPy },
  { lang: 'java', label: 'Java', file: 'DoublyLinkedList.java', code: doublyJava },
  { lang: 'go', label: 'Go', file: 'doubly_linked_list.go', code: doublyGo },
  { lang: 'cpp', label: 'C++', file: 'doubly_linked_list.cpp', code: doublyCpp },
];
