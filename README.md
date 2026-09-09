# 算法手记 · Algo Notes

> 图解数据结构与算法，带分步动画的 LeetCode 题解
> Visual data structures & algorithms notes with animated LeetCode solutions.

### 🌐 在线访问 · Live

## **https://shoujche.github.io/algorithm-notes/**

[![Website](https://img.shields.io/website?url=https%3A%2F%2Fshoujche.github.io%2Falgorithm-notes%2F&label=%E7%AB%99%E7%82%B9&up_message=online&down_message=offline&style=for-the-badge)](https://shoujche.github.io/algorithm-notes/)
[![Built with Astro](https://img.shields.io/badge/Built%20with-Astro-BC52EE?style=for-the-badge&logo=astro&logoColor=white)](https://astro.build)

---

从零开始记录数据结构与算法的学习，用可交互的分步动画拆解每一道经典题。基于 [Astro](https://astro.build) 构建，纯静态，部署在 GitHub Pages。

## 本地开发

```bash
npm install      # 安装依赖
npm run dev      # 启动开发服务器 → http://localhost:4321/algorithm-notes
npm run build    # 构建静态产物到 dist/
npm run preview  # 本地预览构建结果
```

## 源码位置

页面里展示的每段代码都是仓库中**真实、可编辑、可运行**的源文件，网页构建时通过 Vite 的 `?raw` 直接读取文件原文。改文件就等于改网页。

- 链表章节全部源码：[`src/code/linked-list/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/linked-list)

| 文件 | 说明 |
| --- | --- |
| [`linked_list.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/linked_list.py) · [`.java`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/LinkedList.java) · [`.go`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/linked_list.go) · [`.cpp`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/linked_list.cpp) | 单向链表（add_head / add_tail / insert / remove） |
| [`doubly_linked_list.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/doubly_linked_list.py) · [`.java`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/DoublyLinkedList.java) · [`.go`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/doubly_linked_list.go) · [`.cpp`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/doubly_linked_list.cpp) | 双向链表（同上，头尾插入均 O(1)） |
| [`reverse_list.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/reverse_list.py) | 反转链表（LeetCode 206） |
| [`lru_cache.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/linked-list/lru_cache.py) | LRU 缓存（LeetCode 146） |

- 二叉树章节全部源码：[`src/code/binary-tree/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/binary-tree)

| 文件 | 说明 |
| --- | --- |
| [`tree_node.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/tree_node.py) · [`.java`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/TreeNode.java) · [`.go`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/tree_node.go) · [`.cpp`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/tree_node.cpp) | 构建与遍历（前 / 中 / 后序 + 层序） |
| [`level_order.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/level_order.py) | 层序遍历（LeetCode 102） |
| [`zigzag_level_order.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/zigzag_level_order.py) | 锯齿形层序遍历（LeetCode 103） |
| [`right_side_view.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/right_side_view.py) | 右视图（LeetCode 199） |
| [`lowest_common_ancestor.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/lowest_common_ancestor.py) | 最近公共祖先（LeetCode 236） |
| [`is_complete_tree.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/binary-tree/is_complete_tree.py) | 完全性检验（LeetCode 958） |

> 网页上每个代码块右上角的文件名都可点击，会直接跳到上面对应的 GitHub 源文件。
