// 链表代码清单：直接引入 src/code/linked-list/ 下的「真实源文件」。
// 想改代码 / 做实验，直接编辑那些 .py / .java / .go / .cpp 文件即可，
// 网页构建时通过 Vite 的 `?raw` 读取文件原文，改完重新构建就同步更新。

// —— 单向链表 ——
import singlyPy from '../code/linked-list/linked_list.py?raw';
import singlyJava from '../code/linked-list/LinkedList.java?raw';
import singlyGo from '../code/linked-list/linked_list.go?raw';
import singlyCpp from '../code/linked-list/linked_list.cpp?raw';

// —— 双向链表 ——
import doublyPy from '../code/linked-list/doubly_linked_list.py?raw';
import doublyJava from '../code/linked-list/DoublyLinkedList.java?raw';
import doublyGo from '../code/linked-list/doubly_linked_list.go?raw';
import doublyCpp from '../code/linked-list/doubly_linked_list.cpp?raw';

export interface CodeVariant {
  lang: string; // Shiki 高亮语言
  label: string; // 选项卡显示名
  file: string; // 文件名（右侧显示）
  code: string;
}

export const singlyVariants: CodeVariant[] = [
  { lang: 'python', label: 'Python', file: 'linked_list.py', code: singlyPy },
  { lang: 'java', label: 'Java', file: 'LinkedList.java', code: singlyJava },
  { lang: 'go', label: 'Go', file: 'linked_list.go', code: singlyGo },
  { lang: 'cpp', label: 'C++', file: 'linked_list.cpp', code: singlyCpp },
];

export const doublyVariants: CodeVariant[] = [
  { lang: 'python', label: 'Python', file: 'doubly_linked_list.py', code: doublyPy },
  { lang: 'java', label: 'Java', file: 'DoublyLinkedList.java', code: doublyJava },
  { lang: 'go', label: 'Go', file: 'doubly_linked_list.go', code: doublyGo },
  { lang: 'cpp', label: 'C++', file: 'doubly_linked_list.cpp', code: doublyCpp },
];
