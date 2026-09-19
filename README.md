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

- ReAct Agent 章节全部源码：[`src/code/agent/react-agent-loop/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/react-agent-loop)

| 文件 | 说明 |
| --- | --- |
| [`agent_core/contracts.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/contracts.py) | 三种 Agent 共用的提案、审批、运行状态与结果数据契约 |
| [`agent_core/policy.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/policy.py) | deny-by-default 工具分级、审批请求与参数摘要 |
| [`agent_core/checkpoints.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/checkpoints.py) | 暂停/恢复状态的原子化本地检查点存储 |
| [`agent_core/skills.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/skills.py) | 可信 Skill 目录扫描与渐进式正文读取 |
| [`agent_core/mcp_adapter.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/mcp_adapter.py) | 本地 MCP schema、调用结果与 Agent 工具格式之间的适配 |
| [`agent_core/sandbox.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/sandbox.py) | 生成带网络、权限和资源限制的 Docker MCP 启动参数 |
| [`agent_core/workspace.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/workspace.py) | 工作区路径边界、文件工具与受限 argv 命令执行 |
| [`agent_core/openai_loop.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/openai_loop.py) | 纯 OpenAI Responses API 手写 ReAct 循环 |
| [`agent_core/langchain_loop.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/langchain_loop.py) | LangChain `create_agent`、middleware 与审批恢复编排 |
| [`agent_core/langgraph_loop.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/langgraph_loop.py) | 显式 LangGraph 节点、条件边、中断与恢复编排 |
| [`pure_openai.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/pure_openai.py) | 纯 OpenAI SDK 版本的可执行入口 |
| [`langchain_agent.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/langchain_agent.py) | LangChain 版本的可执行入口 |
| [`langgraph_agent.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/langgraph_agent.py) | LangGraph 版本的可执行入口 |
| [`mcp_server.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/mcp_server.py) | 容器内运行、仅使用 stdio 的六工具 MCP Server |
| [`cli.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/cli.py) | 三种实现共用的启动、审批、拒绝与编辑后恢复 CLI |
| [`sandbox/Dockerfile`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/sandbox/Dockerfile) | 非 root、锁定依赖的 MCP 工具沙盒镜像 |
| [`skills/workspace-helper/SKILL.md`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/skills/workspace-helper/SKILL.md) | 页面示例使用的工作区操作 Skill |

## 新增章节

完整流程已固化为 Cursor Skill：[`.cursor/skills/add-algo-chapter`](.cursor/skills/add-algo-chapter/SKILL.md)（登记章节 → 写真实源码 → 建页面/图解/动画 → 更新 README → 构建校验 → 评审后推送）。
