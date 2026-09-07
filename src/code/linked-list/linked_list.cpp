struct ListNode {
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
};
