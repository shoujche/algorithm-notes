// 二叉树代码清单：直接引入 src/code/binary-tree/ 下的真实源文件（`?raw`）。
// 基础章节提供 Python / Java / Go / C++ 四语言；具体题解为 Python。

import type { CodeVariant } from './linked-list-code';

// —— 基础：构建与遍历（多语言）——
import basicsPy from '../code/binary-tree/tree_node.py?raw';
import basicsJava from '../code/binary-tree/TreeNode.java?raw';
import basicsGo from '../code/binary-tree/tree_node.go?raw';
import basicsCpp from '../code/binary-tree/tree_node.cpp?raw';

// —— 题解（Python）——
import levelOrderCode from '../code/binary-tree/level_order.py?raw';
import zigzagCode from '../code/binary-tree/zigzag_level_order.py?raw';
import rightViewCode from '../code/binary-tree/right_side_view.py?raw';
import lcaCode from '../code/binary-tree/lowest_common_ancestor.py?raw';
import completenessCode from '../code/binary-tree/is_complete_tree.py?raw';

export { levelOrderCode, zigzagCode, rightViewCode, lcaCode, completenessCode };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/binary-tree';

export const basicsVariants: CodeVariant[] = [
  { lang: 'python', label: 'Python', file: 'tree_node.py', code: basicsPy },
  { lang: 'java', label: 'Java', file: 'TreeNode.java', code: basicsJava },
  { lang: 'go', label: 'Go', file: 'tree_node.go', code: basicsGo },
  { lang: 'cpp', label: 'C++', file: 'tree_node.cpp', code: basicsCpp },
];
