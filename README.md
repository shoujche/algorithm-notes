# Agent 工程手记 · Agent Engineering Notes

> 从 Python 到 Agent 的学习路线：每个阶段写清要掌握什么，配可运行的代码和面试题
> A learning roadmap from Python engineering and middleware to building and evaluating agents.

### 🌐 在线访问 · Live

## **https://shoujche.github.io/algorithm-notes/**

[![Website](https://img.shields.io/website?url=https%3A%2F%2Fshoujche.github.io%2Falgorithm-notes%2F&label=%E7%AB%99%E7%82%B9&up_message=online&down_message=offline&style=for-the-badge)](https://shoujche.github.io/algorithm-notes/)
[![Built with Astro](https://img.shields.io/badge/Built%20with-Astro-BC52EE?style=for-the-badge&logo=astro&logoColor=white)](https://astro.build)

---

这是一份自己整理的学习路线，分四个板块、11 个阶段：

| 板块 | 阶段 |
| --- | --- |
| Python 工程 | 语言与运行时 → 并发与网络 → 类型与项目结构 → Web 框架 |
| 中间件 | 缓存与消息（Redis、Kafka、RabbitMQ） |
| Agent | 模型与 Agent 原理 → Agent 框架 → 评测与上线 |
| 面试 | 算法 → 手撕代码 → 高频真题 |

每个阶段在首页列出目标和「需要掌握」清单，章节里的代码都是仓库中可以直接运行的源文件。站点基于 [Astro](https://astro.build) 构建，纯静态，部署在 GitHub Pages。路线结构定义在 [`src/data/topics.ts`](src/data/topics.ts) 的 `boards` 里。

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
| [`climb_stairs.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/climb_stairs.py) | 爬楼梯（LeetCode 70）：先填完整 dp 表，再给只留前两格的写法 |
| [`min_cost_climbing_stairs.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/min_cost_climbing_stairs.py) | 最小花费爬楼梯（LeetCode 746） |
| [`max_sub_array.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/max_sub_array.py) | 最大子数组和（LeetCode 53） |
| [`house_robber.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/house_robber.py) | 打家劫舍（LeetCode 198） |
| [`coin_change.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/coin_change.py) | 零钱兑换（LeetCode 322） |
| [`length_of_lis.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/length_of_lis.py) | 最长递增子序列（LeetCode 300），O(n²) 的表 |
| [`longest_common_subsequence.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/longest_common_subsequence.py) | 最长公共子序列（LeetCode 1143） |
| [`min_distance.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/dynamic-programming/min_distance.py) | 编辑距离（LeetCode 72） |

> 网页上每个代码块右上角的文件名都可点击，会直接跳到上面对应的 GitHub 源文件。

- Python 基础「架构里的标准库类型」章节源码：[`src/code/python/stdlib-types/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/python/stdlib-types)。每个文件可直接 `python xxx.py` 运行，只需 Python 3.11+ 标准库。

| 文件 | 说明 |
| --- | --- |
| [`protocol_port.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/python/stdlib-types/protocol_port.py) | `Protocol` 按方法形状接依赖；`ABC` 要求继承 |
| [`literal_alias.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/python/stdlib-types/literal_alias.py) | `Literal`、`Final`、`TypeAlias`，边界上用 `get_args`；`Enum` 自带成员 |
| [`typed_dict_shape.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/python/stdlib-types/typed_dict_shape.py) | `TypedDict`、`NotRequired`、`Annotated` |
| [`collections_abc.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/python/stdlib-types/collections_abc.py) | `Sequence`、`Mapping`、`Callable`、`Awaitable`、`AsyncIterator` |
| [`dataclass_model.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/python/stdlib-types/dataclass_model.py) | `frozen` 值对象、`replace`、`field(default_factory=...)`、`ClassVar` |

- Python 框架板块源码：[`src/code/framework/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/framework)。每个文件都是单文件脚本，直接 `python xxx.py` 运行（Django 用 `settings.configure()` + 内存 SQLite，不需要建项目）。
- 四份长文档（核心用法 · 常用方法 · 教程 · 工程实践 · 面试题）：[`django.md`](https://github.com/shoujche/algorithm-notes/blob/main/docs/python-frameworks/django.md) · [`flask.md`](https://github.com/shoujche/algorithm-notes/blob/main/docs/python-frameworks/flask.md) · [`fastapi.md`](https://github.com/shoujche/algorithm-notes/blob/main/docs/python-frameworks/fastapi.md) · [`libraries.md`](https://github.com/shoujche/algorithm-notes/blob/main/docs/python-frameworks/libraries.md)

| 文件 | 说明 |
| --- | --- |
| [`django/request_cycle.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/django/request_cycle.py) | 中间件洋葱顺序、FBV / CBV、URLconf 与 `reverse` |
| [`django/orm_queries.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/django/orm_queries.py) | 惰性 QuerySet、字段查找、Q / F、annotate / aggregate |
| [`django/n_plus_one.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/django/n_plus_one.py) | 数 SQL 条数：`all()` 7 条、`select_related` 1 条、`prefetch_related` 2 条 |
| [`django/transaction_stock.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/django/transaction_stock.py) | `atomic`、F 条件更新防超卖、`select_for_update`、`on_commit`、savepoint |
| [`django/drf_api.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/django/drf_api.py) | DRF Serializer 校验、ModelViewSet、Router、权限 |
| [`django/async_tasks.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/django/async_tasks.py) | 异步视图与异步 ORM、`SynchronousOnlyOperation`、内置 Tasks 框架 |
| [`flask/app_basics.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/flask/app_basics.py) | 路由、取参数、视图返回值、`url_for`、`abort` |
| [`flask/contexts.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/flask/contexts.py) | 应用 / 请求上下文、`g`、session 可解码、线程隔离 |
| [`flask/factory_blueprint.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/flask/factory_blueprint.py) | 应用工厂、蓝图、扩展 `init_app`、`from_prefixed_env` |
| [`flask/sqlalchemy_crud.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/flask/sqlalchemy_crud.py) | Flask-SQLAlchemy 3.x 模型、`db.select`、`joinedload`、原子扣库存 |
| [`flask/hooks_errors.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/flask/hooks_errors.py) | 钩子执行顺序、短路、统一 JSON 错误 |
| [`flask/testing_async.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/flask/testing_async.py) | 测试工具；真实单线程服务器实测 async 视图不提高吞吐 |
| [`fastapi/concurrency.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/fastapi/concurrency.py) · [`pydantic_demo.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/fastapi/pydantic_demo.py) · [`dependency.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/fastapi/dependency.py) · [`middleware.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/fastapi/middleware.py) · [`streaming.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/fastapi/streaming.py) | FastAPI 并发模型、Pydantic、依赖注入、中间件与 lifespan、流式响应 |
| [`compare/bookshop_django.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/compare/bookshop_django.py) · [`bookshop_flask.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/compare/bookshop_flask.py) · [`bookshop_fastapi.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/compare/bookshop_fastapi.py) | 同一个书店接口的三种写法：创建（校验）/ 查询（404）/ 购买（409） |
| [`libs/peewee_orm.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/libs/peewee_orm.py) | Peewee：`DatabaseProxy`、join / prefetch 的 SQL 条数、条件更新 |
| [`libs/memory_cache.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/libs/memory_cache.py) | cachetools：`TTLCache`、`LRUCache`、带锁的 `@cached` |
| [`libs/shared_cache.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/framework/libs/shared_cache.py) | Django LocMem、Flask-Caching SimpleCache、redis-py 的 `get_or_set` |

数据库与缓存的选型说明（SQLAlchemy、Peewee、cachetools、Redis、Memcached，以及三个框架怎么接）：[`libraries.md`](https://github.com/shoujche/algorithm-notes/blob/main/docs/python-frameworks/libraries.md)。

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

- LangGraph 核心用法章节源码：[`src/code/agent/langgraph/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/langgraph)

| 文件 | 说明 |
| --- | --- |
| [`minimal_graph.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/minimal_graph.py) | 最小状态图：状态、节点、条件边、invoke |
| [`command_from_node.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/command_from_node.py) | 节点 return `Command(update=..., goto=...)` |
| [`command_parent.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/command_parent.py) | `graph=Command.PARENT`：子图把命令发给父图 |
| [`interrupt_resume.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/interrupt_resume.py) | `interrupt` 的 payload 送出，`Command(resume=)` 作为它的返回值 |
| [`replay.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/replay.py) | 恢复时节点从头重跑 |
| [`multi_interrupt.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/multi_interrupt.py) | 同一节点按顺序恢复；并行挂起用 interrupt id |
| [`approval_route.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/approval_route.py) | 审批后用 `goto` 跳分支 |
| [`breakpoint.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/breakpoint.py) | `interrupt_before`，用 `invoke(None)` 继续 |
| [`update_state.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/update_state.py) | `get_state` / `update_state` |
| [`time_travel.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/time_travel.py) | 从旧检查点分叉 |
| [`message_thread.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/message_thread.py) | `MessagesState` + 同一个 `thread_id` |
| [`tool_loop.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/tool_loop.py) | 模型节点、`ToolNode`、`tools_condition` |
| [`preset_agent.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/preset_agent.py) | `create_agent` 编出的 LangGraph 图 |
| [`run_controls.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/run_controls.py) | 步数上限、重试、落盘与流式 |
| [`send_fanout.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/send_fanout.py) | `Send` 扇出 |
| [`memory_store.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/langgraph/memory_store.py) | 检查点按线程，Store 跨线程 |

- LlamaIndex 核心用法章节源码：[`src/code/agent/llamaindex/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/llamaindex)

| 文件 | 说明 |
| --- | --- |
| [`keyword_embed.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/keyword_embed.py) | 用词是否出现代替 embedding，并准备两份酒店 Document |
| [`split_nodes.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/split_nodes.py) | SentenceSplitter 把一份 Document 切成 Node |
| [`index_retrieve.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/index_retrieve.py) | VectorStoreIndex 与 Retriever，分数为 0 不算查到 |
| [`query_engine.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/query_engine.py) | Query Engine 把检索到的原文交给 LLM |
| [`metadata_filter.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/metadata_filter.py) | 向量相似度之外的 metadata 硬条件 |
| [`ingestion.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/ingestion.py) | IngestionPipeline 把切块和向量写明 |
| [`workflow_rag.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/llamaindex/workflow_rag.py) | Workflow 把检索和作答分成两步 |

- 组件专题源码：[`src/code/component/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/component)。页面按教程写：先讲一个用法，再给对应的 Python。Redis 命令可用 fakeredis 在本地执行；Kafka / RabbitMQ 的客户端函数要有本机服务才发送，文件直接运行时只检查配置。

| 文件 | 说明 |
| --- | --- |
| [`redis/connect_kv.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/redis/connect_kv.py) | `SET` 带过期、`INCR`、pipeline |
| [`redis/structures.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/redis/structures.py) | 哈希、列表、集合、有序集合 |
| [`redis/dist_lock.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/redis/dist_lock.py) | `SET key token NX PX`、Lua 解锁与续期 |
| [`redis/cache_aside.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/redis/cache_aside.py) | 旁路缓存、空值、锁住装载、错开 TTL |
| [`kafka/consumer_group.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/kafka/consumer_group.py) | 分区日志；消费组按 Range 分配，多出的消费者空闲 |
| [`kafka/producer_client.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/kafka/producer_client.py) | `acks`、`linger.ms`、`batch.size`、压缩、幂等生产者 |
| [`kafka/batch_acks.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/kafka/batch_acks.py) | 批量把多次发送收成少数写入；`acks` 等几个副本 |
| [`kafka/consumer_client.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/kafka/consumer_client.py) | 关闭自动提交，处理完再 `commit` |
| [`kafka/manual_commit.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/kafka/manual_commit.py) | 崩溃后从上次位点再读；并发只推进连续水位 |
| [`rabbitmq/publish_client.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/rabbitmq/publish_client.py) | 连接、通道、声明、持久化与发布确认 |
| [`rabbitmq/exchange_route.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/rabbitmq/exchange_route.py) | direct、topic（`*` / `#`）、fanout |
| [`rabbitmq/confirm_ack.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/rabbitmq/confirm_ack.py) | 持久化后确认；未 ack 则带 `redelivered` 重投 |
| [`rabbitmq/consume_client.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/rabbitmq/consume_client.py) | 手动 ack、prefetch、死信、按 `message_id` 去重 |
| [`rabbitmq/idempotent_consumer.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/component/rabbitmq/idempotent_consumer.py) | 重投第二次只确认，业务列表仍是一行 |

- Deep Agents 核心用法章节源码：[`src/code/agent/deepagents/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/deepagents)

| 文件 | 说明 |
| --- | --- |
| [`filesystem_notes.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/deepagents/filesystem_notes.py) | 脚本模型调用 write_file / read_file，文件留在当前线程状态 |
| [`path_permissions.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/deepagents/path_permissions.py) | FilesystemPermission 按顺序匹配，拒绝 /private/** 的写入 |
| [`subagent_task.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/deepagents/subagent_task.py) | task 子代理只把最终结论交回父代理 |
| [`memory_store.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/deepagents/memory_store.py) | /memories/ 走 StoreBackend，换 thread_id 仍可读 |
| [`approve_write.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/deepagents/approve_write.py) | interrupt_on 暂停 write_file，批准后同一条线程继续 |

- Agent 评测与 Benchmark 章节源码：[`src/code/agent/agent-eval/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/agent/agent-eval)

| 文件 | 说明 |
| --- | --- |
| [`eval_harness.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/eval_harness.py) | 数据集 → 被测 agent → 轨迹 → 评估器 → 分组报告 → 对比基线的门槛 |
| [`retrieval_metrics.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/retrieval_metrics.py) | Recall@k、Precision@k、Hit Rate、MRR、nDCG，chunk 折回文档再算 |
| [`rag_judge.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/rag_judge.py) | 拆陈述的 faithfulness、context precision / recall，裁判可替换 |
| [`memory_probe.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/memory_probe.py) | 抽取、跨会话、更新、时间、拒答五类探针，对比朴素与版本化记忆 |
| [`trajectory_match.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/trajectory_match.py) | 五种轨迹匹配、工具选择 precision / recall、pass@k 与 pass^k |
| [`judge_calibration.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/judge_calibration.py) | Cohen's kappa 校准裁判，成对比较双向判消除位置偏差 |
| [`stats_gate.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/stats_gate.py) | 二项区间、bootstrap、配对差值区间和三档发布门槛 |
| [`ragas_metrics.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/ragas_metrics.py) | RAGAS 0.4 collections 指标的 ascore 写法（需模型密钥） |
| [`test_deepeval_agent.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/test_deepeval_agent.py) | DeepEval 4.3 pytest 用例：RAG 指标、工具正确性、GEval |
| [`inspect_task.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/inspect_task.py) | Inspect AI Task：工具、自定义 scorer、epochs 与 pass_at_2 |
| [`langsmith_experiment.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/langsmith_experiment.py) | LangSmith 数据集、evaluator、summary evaluator、重复实验 |
| [`promptfooconfig.yaml`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/promptfooconfig.yaml) | promptfoo 两版 prompt × 两个模型，确定性断言加裁判断言 |
| [`online_eval.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/agent/agent-eval/online_eval.py) | OpenTelemetry GenAI span、规则全量、裁判抽样、低分进复核队列 |

## 新增章节

完整流程已固化为 Cursor Skill：[`.cursor/skills/add-algo-chapter`](.cursor/skills/add-algo-chapter/SKILL.md)（登记章节 → 写真实源码 → 建页面/图解/动画 → 更新 README → 构建校验 → 评审后推送）。
