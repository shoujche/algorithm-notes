struct DListNode {
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
};
