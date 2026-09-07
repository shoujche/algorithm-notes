class ListNode {
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
}
