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

- 动态规划章节全部源码：[`src/code/dynamic-programming/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/dynamic-programming)

| 文件 | 说明 |
| --- | --- |
| [`climb_stairs.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/climb_stairs.py) | 爬楼梯的方法数（LeetCode 70） |
| [`min_cost_climbing_stairs.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/min_cost_climbing_stairs.py) | 使用最小花费爬楼梯（LeetCode 746） |
| [`house_robber.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/house_robber.py) | 打家劫舍（LeetCode 198） |

> 网页上每个代码块右上角的文件名都可点击，会直接跳到上面对应的 GitHub 源文件。

- ReAct Agent 章节全部源码：[`src/code/agent/react-agent-loop/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/react-agent-loop)

| 文件 | 说明 |
| --- | --- |
| [`agent_core/contracts.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/contracts.py) | 三种 Agent 共用的提案、审批、运行状态与结果数据契约 |
| [`agent_core/policy.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/policy.py) | deny-by-default 工具分级、审批请求、参数摘要与恒时 digest 比对 |
| [`agent_core/approval_cli.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/approval_cli.py) | 三个入口共用的决策参数、`--expect-digest` 校验与恢复决策构造 |
| [`agent_core/checkpoints.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/checkpoints.py) | 暂停/恢复状态的原子化本地检查点存储 |
| [`agent_core/side_effects.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/agent_core/side_effects.py) | 三版共用、不依赖任何框架的副作用账本：`claimed` / `executed` / `failed` 状态机与原子落盘 |
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
| [`cli.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/cli.py) | 三种实现共用的启动、审批、拒绝与编辑后恢复 CLI（含按片段脱敏的暂停输出） |
| [`sandbox/Dockerfile`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/sandbox/Dockerfile) | 非 root、锁定依赖的 MCP 工具沙盒镜像 |
| [`skills/workspace-helper/SKILL.md`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/react-agent-loop/skills/workspace-helper/SKILL.md) | 页面示例使用的工作区操作 Skill |
| [`workspace/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/react-agent-loop/workspace) | 三个入口与 CLI 的默认工作区（唯一挂载进容器的可写目录，内容不入库） |

- Agent 理论基础章节源码：[`src/code/agent/agent-theory/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/agent-theory)

| 文件 | 说明 |
| --- | --- |
| [`decode.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-theory/decode.py) | Top-P（Nucleus）采样：按累积概率选出候选 token |

- RAG 面试章节源码：[`src/code/agent/rag-interview/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/rag-interview)

| 文件 | 说明 |
| --- | --- |
| [`chunking.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/rag-interview/chunking.py) | 带重叠的滑动窗口切块 |
| [`rrf.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/rag-interview/rrf.py) | Reciprocal Rank Fusion：融合多路排序 |
| [`time_decay.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/rag-interview/time_decay.py) | 相关性与时间新鲜度组合排序 |
| [`retrieval_pipeline.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/rag-interview/retrieval_pipeline.py) | 召回、过滤、组装生成上下文的最小骨架 |

- Agent 手撕代码章节源码：[`src/code/agent/agent-hands-on/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/agent-hands-on)

| 文件 | 说明 |
| --- | --- |
| [`react_agent.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-hands-on/react_agent.py) | 最小 ReAct 循环：Thought → Action → Observation，模型输出用规则模拟 |
| [`tool_registry.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-hands-on/tool_registry.py) | 按名字查找工具、校验参数、统一执行 |
| [`memory.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-hands-on/memory.py) | 短期对话列表与演示用哈希向量检索，不接外部 API |
| [`cot.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-hands-on/cot.py) | Chain-of-Thought prompt 与最终答案抽取 |
| [`reflection.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-hands-on/reflection.py) | 草稿、检查清单打分、带批评重写 |
| [`chunking.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-hands-on/chunking.py) | 固定窗口、重叠窗口、按段落/句子边界切块 |

Agent 核心真题（A04）是问答页，没有单独源码文件。

## 新增章节

完整流程已固化为 Cursor Skill：[`.cursor/skills/add-algo-chapter`](.cursor/skills/add-algo-chapter/SKILL.md)（登记章节 → 写真实源码 → 建页面/图解/动画 → 更新 README → 构建校验 → 评审后推送）。
