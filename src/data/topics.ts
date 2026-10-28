// 章节注册表：首页路线、顶部导航与侧边栏都从这里生成。
// 加新章节：在 chapters 登记、新建页面，再把 slug 放进 boards 里某个阶段。

export const SITE = {
  name: 'Agent 工程手记',
  en: 'Agent Engineering Notes',
  logo: 'AE',
  tagline: '从 Python 到 Agent 的学习路线',
  description: '一条从 Python 工程、中间件到 Agent 开发与评测的学习路线：每个阶段写清要掌握什么，配可运行的代码和面试题。',
};

export type Difficulty = 'base' | 'easy' | 'mid' | 'hard';

export const categoryKeys = ['algo', 'python', 'framework', 'component', 'agent'] as const;
export type Category = (typeof categoryKeys)[number];

export interface Section {
  id: string;        // 页内锚点 id
  num: string;       // 序号，如 "01"
  label: string;     // 显示名
  lc?: string;       // LeetCode 题号
  lcSlug?: string;   // leetcode.cn 题目 slug，用于打开原题描述
}

export interface Chapter {
  slug: string;      // 路由由 categoryConfig 中的 routePrefix 统一决定
  category: Category; // 归属板块：算法 / Python 基础 / Python 框架 / 组件 / Agent
  num: string;       // 章节序号
  cn: string;        // 中文名
  en: string;        // 英文名
  summary: string;   // 首页卡片简介
  sections?: Section[]; // 页内小节（用于侧边栏 + 首页展示）
  ready: boolean;    // 是否已完成
}

export const chapters: Chapter[] = [
  {
    slug: 'linked-list',
    category: 'algo',
    num: '01',
    cn: '链表',
    en: 'Linked List',
    summary: '从指针理解数据结构：单向、双向链表，动画拆解链表反转与 LRU 缓存。',
    ready: true,
    sections: [
      { id: 'singly', num: '01', label: '单向链表' },
      { id: 'doubly', num: '02', label: '双向链表' },
      { id: 'reverse', num: '03', label: '链表反转', lc: '206', lcSlug: 'reverse-linked-list' },
      { id: 'lru', num: '04', label: 'LRU 缓存', lc: '146', lcSlug: 'lru-cache' },
    ],
  },
  { slug: 'stack-queue', category: 'algo', num: '02', cn: '栈与队列', en: 'Stack & Queue', summary: '规划中。', ready: false },
  {
    slug: 'binary-tree',
    category: 'algo',
    num: '03',
    cn: '二叉树',
    en: 'Binary Tree',
    summary: '从构建与遍历入手，动画拆解 BFS 层序，攻克锯齿形层序、右视图、最近公共祖先与完全性检验。',
    ready: true,
    sections: [
      { id: 'basics', num: '01', label: '构建与遍历' },
      { id: 'level-order', num: '02', label: '层序遍历', lc: '102', lcSlug: 'binary-tree-level-order-traversal' },
      { id: 'zigzag', num: '03', label: '锯齿形层序', lc: '103', lcSlug: 'binary-tree-zigzag-level-order-traversal' },
      { id: 'right-view', num: '04', label: '右视图', lc: '199', lcSlug: 'binary-tree-right-side-view' },
      { id: 'lca', num: '05', label: '最近公共祖先', lc: '236', lcSlug: 'lowest-common-ancestor-of-a-binary-tree' },
      { id: 'completeness', num: '06', label: '完全性检验', lc: '958', lcSlug: 'check-completeness-of-a-binary-tree' },
    ],
  },
  {
    slug: 'dynamic-programming',
    category: 'algo',
    num: '04',
    cn: '动态规划',
    en: 'Dynamic Programming',
    summary: '先把整张 dp 表填出来：爬楼梯、最小花费、最大子数组和、打家劫舍，再到零钱兑换、上升子序列、公共子序列和编辑距离。',
    ready: true,
    sections: [
      { id: 'climb-stairs', num: '01', label: '爬楼梯', lc: '70', lcSlug: 'climbing-stairs' },
      { id: 'min-cost', num: '02', label: '最小花费爬楼梯', lc: '746', lcSlug: 'min-cost-climbing-stairs' },
      { id: 'max-subarray', num: '03', label: '最大子数组和', lc: '53', lcSlug: 'maximum-subarray' },
      { id: 'house-robber', num: '04', label: '打家劫舍', lc: '198', lcSlug: 'house-robber' },
      { id: 'coin-change', num: '05', label: '零钱兑换', lc: '322', lcSlug: 'coin-change' },
      { id: 'lis', num: '06', label: '最长递增子序列', lc: '300', lcSlug: 'longest-increasing-subsequence' },
      { id: 'lcs', num: '07', label: '最长公共子序列', lc: '1143', lcSlug: 'longest-common-subsequence' },
      { id: 'edit-distance', num: '08', label: '编辑距离', lc: '72', lcSlug: 'edit-distance' },
    ],
  },

  // ===== Python 板块 =====
  { slug: 'py-basics', category: 'python', num: 'P01', cn: '语言基础', en: 'Language Basics', summary: '可变/不可变、is vs ==、深浅拷贝、参数传递等 Python 基本功。', ready: true,
    sections: [
      { id: 'mutable', num: '01', label: '可变 vs 不可变' },
      { id: 'is-eq', num: '02', label: 'is vs ==' },
      { id: 'copy', num: '03', label: '深浅拷贝' },
      { id: 'args', num: '04', label: '参数传递机制' },
      { id: 'default-arg', num: '05', label: '可变默认参数陷阱' },
      { id: 'closure', num: '06', label: '闭包与延迟绑定' },
      { id: 'duck-typing', num: '07', label: '鸭子类型' },
      { id: 'class-static', num: '08', label: 'staticmethod 与 classmethod' },
    ],
  },
  { slug: 'data-model', category: 'python', num: 'P02', cn: '数据模型与高级特性', en: 'Data Model', summary: '魔术方法、装饰器、生成器/迭代器、上下文管理器、描述符。', ready: true,
    sections: [
      { id: 'dunder', num: '01', label: '魔术方法与数据模型' },
      { id: 'decorator', num: '02', label: '装饰器' },
      { id: 'iterator', num: '03', label: '迭代器与生成器' },
      { id: 'context', num: '04', label: '上下文管理器' },
      { id: 'descriptor', num: '05', label: '描述符与 property' },
      { id: 'introspection', num: '06', label: '自省与反射' },
      { id: 'singleton', num: '07', label: '单例模式' },
    ],
  },
  { slug: 'memory-gc', category: 'python', num: 'P03', cn: '内存管理与 GC', en: 'Memory & GC', summary: '引用计数、循环引用、分代 GC、__slots__ 优化。', ready: true,
    sections: [
      { id: 'refcount', num: '01', label: '引用计数' },
      { id: 'cycle', num: '02', label: '循环引用问题' },
      { id: 'gc', num: '03', label: '分代垃圾回收' },
      { id: 'weakref', num: '04', label: '弱引用' },
      { id: 'slots', num: '05', label: '__slots__ 优化' },
    ],
  },
  { slug: 'concurrency-gil', category: 'python', num: 'P04', cn: '并发与 GIL', en: 'Concurrency & GIL', summary: 'GIL 原理与调度，线程/进程/协程对比与选型。', ready: true,
    sections: [
      { id: 'what-is-gil', num: '01', label: 'GIL 是什么' },
      { id: 'scheduling', num: '02', label: 'GIL 如何调度' },
      { id: 'cpu-vs-io', num: '03', label: 'CPU 密集 vs I/O 密集' },
      { id: 'race', num: '04', label: '有 GIL 为何还要锁' },
      { id: 'choose', num: '05', label: '线程/进程/协程选型' },
    ],
  },
  { slug: 'asyncio', category: 'python', num: 'P05', cn: 'asyncio 深入', en: 'Asyncio', summary: '事件循环、协程调度、async/await 原理与常见坑。', ready: true,
    sections: [
      { id: 'why-async', num: '01', label: '为什么需要 asyncio' },
      { id: 'event-loop', num: '02', label: '事件循环原理' },
      { id: 'coroutine', num: '03', label: '协程与 async/await' },
      { id: 'gather', num: '04', label: '并发:gather' },
      { id: 'pitfalls', num: '05', label: '常见坑:阻塞事件循环' },
    ],
  },
  { slug: 'network-streaming', category: 'python', num: 'P06', cn: '网络与流式', en: 'Network & Streaming', summary: 'HTTP 基础、SSE vs WebSocket、流式输出。', ready: true,
    sections: [
      { id: 'http', num: '01', label: 'HTTP 基础与常见状态码' },
      { id: 'sse-vs-ws', num: '02', label: 'SSE vs WebSocket' },
      { id: 'streaming', num: '03', label: '流式输出原理' },
      { id: 'backpressure', num: '04', label: '背压与超时' },
    ],
  },
  { slug: 'hands-on', category: 'python', num: 'P07', cn: '实战手撕', en: 'Hands-on Coding', summary: '手写装饰器、异步限流器、简易 tool-calling loop 等经典手撕题。', ready: true,
    sections: [
      { id: 'timer-decorator', num: '01', label: '手写计时/重试装饰器' },
      { id: 'lru', num: '02', label: '手写 LRU 缓存', lc: '146', lcSlug: 'lru-cache' },
      { id: 'rate-limiter', num: '03', label: '异步限流器' },
      { id: 'async-pool', num: '04', label: '异步并发池' },
      { id: 'tool-loop', num: '05', label: '简易 tool-calling loop' },
    ],
  },
  {
    slug: 'stdlib-types',
    category: 'python',
    num: 'P08',
    cn: '架构里的标准库类型',
    en: 'Stdlib Types',
    summary: '用 Protocol、Literal、TypedDict、collections.abc 和 dataclass 描述端口、配置和值对象。标准库即可，Python 3.11+。',
    ready: true,
    sections: [
      { id: 'protocol', num: '01', label: 'Protocol 与 ABC' },
      { id: 'literal', num: '02', label: 'Literal 与 Enum' },
      { id: 'typed-dict', num: '03', label: 'TypedDict' },
      { id: 'abc', num: '04', label: 'collections.abc' },
      { id: 'dataclass', num: '05', label: 'dataclass' },
    ],
  },

  // ===== Python 框架板块 =====
  {
    slug: 'django',
    category: 'framework',
    num: 'F01',
    cn: 'Django 核心用法',
    en: 'Django',
    summary: '请求生命周期、ORM 与 N+1、事务防超卖、DRF、异步视图与内置 Tasks，每节附与 Flask / FastAPI 的对照。',
    ready: true,
    sections: [
      { id: 'request-cycle', num: '01', label: '请求生命周期与中间件' },
      { id: 'orm', num: '02', label: 'ORM 与惰性 QuerySet' },
      { id: 'n-plus-one', num: '03', label: 'N+1 与预加载' },
      { id: 'transaction', num: '04', label: '事务与防超卖' },
      { id: 'drf', num: '05', label: 'DRF 序列化与视图集' },
      { id: 'async-tasks', num: '06', label: '异步视图与后台任务' },
      { id: 'compare', num: '07', label: '同一接口三种写法' },
    ],
  },
  {
    slug: 'flask',
    category: 'framework',
    num: 'F02',
    cn: 'Flask 核心用法',
    en: 'Flask',
    summary: '路由与返回值、应用 / 请求上下文、应用工厂与蓝图、Flask-SQLAlchemy、钩子与错误处理、async 视图的真相。',
    ready: true,
    sections: [
      { id: 'basics', num: '01', label: '路由与视图返回值' },
      { id: 'context', num: '02', label: '应用上下文与请求上下文' },
      { id: 'factory', num: '03', label: '应用工厂与蓝图' },
      { id: 'sqlalchemy', num: '04', label: 'Flask-SQLAlchemy' },
      { id: 'hooks', num: '05', label: '钩子与统一错误' },
      { id: 'testing-async', num: '06', label: '测试与 async 视图' },
      { id: 'compare', num: '07', label: '同一接口三种写法' },
    ],
  },
  {
    slug: 'fastapi',
    category: 'framework',
    num: 'F03',
    cn: 'FastAPI 工程',
    en: 'FastAPI',
    summary: '并发模型、Pydantic、依赖注入、中间件与生命周期、流式响应，每节附与 Django / Flask 的对照。',
    ready: true,
    sections: [
      { id: 'concurrency-model', num: '01', label: '并发模型:async vs sync 路由' },
      { id: 'pydantic', num: '02', label: 'Pydantic 数据校验' },
      { id: 'di', num: '03', label: '依赖注入' },
      { id: 'middleware', num: '04', label: '中间件与生命周期' },
      { id: 'streaming', num: '05', label: '流式响应' },
      { id: 'compare', num: '06', label: '同一接口三种写法' },
    ],
  },
  {
    slug: 'libraries',
    category: 'framework',
    num: 'F04',
    cn: '常用第三方库',
    en: 'Libraries',
    summary: '数据库选 SQLAlchemy 还是 Peewee，缓存用进程内的 cachetools，还是 Redis / Memcached，以及三个框架各自怎么接。',
    ready: true,
    sections: [
      { id: 'peewee', num: '01', label: 'Peewee 与三种 ORM' },
      { id: 'memory-cache', num: '02', label: '进程内缓存 cachetools' },
      { id: 'shared-cache', num: '03', label: 'Redis 与框架缓存' },
      { id: 'choose', num: '04', label: '怎么选' },
    ],
  },

  // ===== Agent 板块 =====
  {
    slug: 'react-agent-loop',
    category: 'agent',
    num: 'A01',
    cn: 'ReAct Agent 循环',
    en: 'ReAct Agent Loop',
    summary: '从最小循环到 Skills、MCP、Docker 沙盒与 Human-in-the-loop，对比三种 Agent 编排方式。',
    ready: true,
    sections: [
      { id: 'mental-model', num: '01', label: 'ReAct 最小心智模型' },
      { id: 'state', num: '02', label: '状态与退出条件' },
      { id: 'skills', num: '03', label: 'Skills 渐进式披露' },
      { id: 'mcp', num: '04', label: 'MCP 工具调用' },
      { id: 'sandbox', num: '05', label: 'Docker 信任边界' },
      { id: 'openai-sdk', num: '06', label: 'OpenAI SDK 手写循环' },
      { id: 'langchain', num: '07', label: 'LangChain Agent' },
      { id: 'langgraph', num: '08', label: 'LangGraph 状态图' },
      { id: 'hitl', num: '09', label: '暂停、审批与恢复' },
      { id: 'comparison', num: '10', label: '三版对比与选型' },
    ],
  },
  {
    slug: 'agent-theory',
    category: 'agent',
    num: 'A02',
    cn: 'Agent 理论基础',
    en: 'Agent Theory',
    summary: '开发岗口径讲注意力、解码、KV Cache、LoRA / vLLM 与 SFT / 对齐，公式点到能解释参数。',
    ready: true,
    sections: [
      { id: 'transformer', num: '01', label: 'Transformer 与注意力' },
      { id: 'decode', num: '02', label: '解码策略与词元化' },
      { id: 'ability', num: '03', label: '模型能力与现象' },
      { id: 'inference', num: '04', label: '推理与微调工程' },
      { id: 'vlm', num: '05', label: 'VLM：对齐、幻觉、应用' },
      { id: 'align', num: '06', label: 'SFT 与对齐' },
    ],
  },
  {
    slug: 'rag-interview',
    category: 'agent',
    num: 'A03',
    cn: 'RAG 面试真题',
    en: 'RAG Interview',
    summary: '22 道 RAG 真题：切块、混合检索、评测与上线取舍，附最小可运行示例。',
    ready: true,
    sections: [
      { id: 'core', num: '01', label: '完整链路' },
      { id: 'retrieval', num: '02', label: '召回与排序' },
      { id: 'evaluation', num: '03', label: '检索错与生成错' },
      { id: 'engineering', num: '04', label: '生产系统' },
      { id: 'advanced', num: '05', label: '可上线策略' },
      { id: 'tools', num: '06', label: 'Function Calling 与 MCP' },
    ],
  },
  {
    slug: 'agent-interview',
    category: 'agent',
    num: 'A04',
    cn: 'Agent 核心真题',
    en: 'Agent Interview',
    summary: '开发岗口径讲 Agent 循环、记忆、工具容错、并发隔离与安全护栏。',
    ready: true,
    sections: [
      { id: 'basics', num: '01', label: '定义、ReAct、规划' },
      { id: 'memory', num: '02', label: '短期对话与长期检索' },
      { id: 'tools', num: '03', label: '工具接入与失败' },
      { id: 'frameworks', num: '04', label: '选型、隔离、线程安全' },
      { id: 'multi', num: '05', label: 'Multi-Agent' },
      { id: 'safety', num: '06', label: '挑战、对齐、隐私' },
      { id: 'prod', num: '07', label: '调度、评估与迭代' },
    ],
  },
  {
    slug: 'agent-hands-on',
    category: 'agent',
    num: 'A05',
    cn: 'Agent 手撕代码',
    en: 'Agent Hands-on',
    summary: '五道白板手撕：ReAct、工具注册与记忆、CoT、自我反思、切块。不接真实模型。',
    ready: true,
    sections: [
      { id: 'react', num: '01', label: '手撕 ReAct Agent' },
      { id: 'registry-memory', num: '02', label: 'Tool Registry 与记忆' },
      { id: 'cot', num: '03', label: 'Chain-of-Thought' },
      { id: 'reflect', num: '04', label: 'Self-Reflection' },
      { id: 'chunk', num: '05', label: '三种切块' },
    ],
  },
  {
    slug: 'langgraph',
    category: 'agent',
    num: 'A06',
    cn: 'LangGraph 核心用法',
    en: 'LangGraph',
    summary: '从 Command 和断点两种暂停，到同一条线程的消息、工具循环、重试与流式、Send 扇出，以及 Store 和检查点各记什么。',
    ready: true,
    sections: [
      { id: 'graph', num: '01', label: '最小状态图' },
      { id: 'command', num: '02', label: 'Command 四个参数' },
      { id: 'interrupt', num: '03', label: 'resume 流回 interrupt' },
      { id: 'replay', num: '04', label: '恢复时整段重跑' },
      { id: 'multi', num: '05', label: '多次 interrupt' },
      { id: 'route', num: '06', label: '审批后动态路由' },
      { id: 'breakpoint', num: '07', label: '断点与 invoke(None)' },
      { id: 'edit-state', num: '08', label: '查看并改状态' },
      { id: 'fork', num: '09', label: '检查点分叉' },
      { id: 'thread', num: '10', label: '同一条线程' },
      { id: 'tools', num: '11', label: '工具循环' },
      { id: 'controls', num: '12', label: '重试、落盘与流式' },
      { id: 'fanout', num: '13', label: 'Send 与 Store' },
    ],
  },
  {
    slug: 'llamaindex',
    category: 'agent',
    num: 'A07',
    cn: 'LlamaIndex 核心用法',
    en: 'LlamaIndex',
    summary: '把原文切成节点、建向量索引、按 metadata 过滤，再用 Query Engine 和 Workflow 取出带来源的答案。不调用真实模型。',
    ready: true,
    sections: [
      { id: 'embed', num: '01', label: '用词当向量' },
      { id: 'split', num: '02', label: '切成节点' },
      { id: 'index', num: '03', label: '索引与检索' },
      { id: 'query', num: '04', label: 'Query Engine' },
      { id: 'filter', num: '05', label: 'Metadata 过滤' },
      { id: 'pipeline', num: '06', label: '入库流水线' },
      { id: 'workflow', num: '07', label: 'Workflow 两步' },
    ],
  },
  {
    slug: 'deepagents',
    category: 'agent',
    num: 'A08',
    cn: 'Deep Agents 核心用法',
    en: 'Deep Agents',
    summary: 'create_deep_agent 在 LangGraph 上带上虚拟文件、路径权限、子代理、跨线程记忆，以及写文件前的人工审批。脚本模型，不调用真实 API。',
    ready: true,
    sections: [
      { id: 'harness', num: '01', label: '套在图上的能力' },
      { id: 'files', num: '02', label: '虚拟文件系统' },
      { id: 'permissions', num: '03', label: '路径权限' },
      { id: 'subagent', num: '04', label: '子代理 task' },
      { id: 'memory', num: '05', label: '跨线程记忆' },
      { id: 'approval', num: '06', label: '写之前先审批' },
    ],
  },
  {
    slug: 'agent-eval',
    category: 'agent',
    num: 'A09',
    cn: 'Agent 评测与 Benchmark',
    en: 'Agent Evaluation',
    summary: '从评测分层和 harness 讲起，手写 RAG 检索与生成指标、记忆探针、工具轨迹匹配、pass^k、裁判校准和 bootstrap 门槛，再对照 RAGAS、DeepEval、Inspect、LangSmith、promptfoo 与线上 OpenTelemetry 评估。',
    ready: true,
    sections: [
      { id: 'layers', num: '01', label: '评测分层与 harness' },
      { id: 'dataset', num: '02', label: '评测集怎么来' },
      { id: 'retrieval', num: '03', label: 'RAG 检索指标' },
      { id: 'generation', num: '04', label: 'RAG 生成指标' },
      { id: 'memory', num: '05', label: '记忆评测' },
      { id: 'tools', num: '06', label: '工具调用与轨迹' },
      { id: 'judge', num: '07', label: 'LLM 裁判与校准' },
      { id: 'stats', num: '08', label: '统计与发布门槛' },
      { id: 'benchmarks', num: '09', label: '公开 Benchmark' },
      { id: 'metric-libs', num: '10', label: '指标库：RAGAS / DeepEval' },
      { id: 'platforms', num: '11', label: '运行器与平台' },
      { id: 'online', num: '12', label: '线上评估闭环' },
    ],
  },

  // ===== 组件板块 =====
  {
    slug: 'redis',
    category: 'component',
    num: 'C01',
    cn: 'Redis',
    en: 'Redis',
    summary: '从键、过期和五种结构写起，再写 SET NX PX 分布式锁，以及旁路缓存怎么对付穿透、击穿和雪崩。',
    ready: true,
    sections: [
      { id: 'keys', num: '01', label: '键、过期与管道' },
      { id: 'types', num: '02', label: '五种结构' },
      { id: 'lock', num: '03', label: '分布式锁' },
      { id: 'cache', num: '04', label: '旁路缓存' },
    ],
  },
  {
    slug: 'kafka',
    category: 'component',
    num: 'C02',
    cn: 'Kafka',
    en: 'Kafka',
    summary: '分区、副本和消费组怎么配合，生产者靠批量与 acks 提高吞吐，消费者处理完再提交位点。',
    ready: true,
    sections: [
      { id: 'group', num: '01', label: '分区、副本、消费组' },
      { id: 'batch', num: '02', label: '生产者与高吞吐' },
      { id: 'commit', num: '03', label: '消费、位点与并发' },
    ],
  },
  {
    slug: 'rabbitmq',
    category: 'component',
    num: 'C03',
    cn: 'RabbitMQ',
    en: 'RabbitMQ',
    summary: '连接、通道和三种交换机，发布确认与手动 ack 怎么保住消息，再用 message_id、死信和 prefetch 处理重复与堆积。',
    ready: true,
    sections: [
      { id: 'route', num: '01', label: '连接、通道、交换机' },
      { id: 'ack', num: '02', label: '确认与不丢' },
      { id: 'idem', num: '03', label: '幂等、死信、prefetch' },
    ],
  },
];

export const readyChapters = chapters.filter((c) => c.ready);
export const soonChapters = chapters.filter((c) => !c.ready);

// 按板块派生
export const algoChapters = chapters.filter((c) => c.category === 'algo');
export const pythonChapters = chapters.filter((c) => c.category === 'python');
export const frameworkChapters = chapters.filter((c) => c.category === 'framework');
export const componentChapters = chapters.filter((c) => c.category === 'component');
export const agentChapters = chapters.filter((c) => c.category === 'agent');

interface CategoryConfig {
  key: Category;
  label: { cn: string; en: string };
  routePrefix: `/${string}`;
  chapters: Chapter[];
}

// category 只决定 URL 前缀；页面怎么分组展示由下面的 boards 决定。
export const categoryConfig: CategoryConfig[] = [
  {
    key: 'algo',
    label: { cn: '算法', en: 'Algorithms' },
    routePrefix: '/topics',
    chapters: algoChapters,
  },
  {
    key: 'python',
    label: { cn: 'Python 基础', en: 'Python Basics' },
    routePrefix: '/python',
    chapters: pythonChapters,
  },
  {
    key: 'framework',
    label: { cn: 'Python 框架', en: 'Python Frameworks' },
    routePrefix: '/framework',
    chapters: frameworkChapters,
  },
  {
    key: 'component',
    label: { cn: '组件', en: 'Components' },
    routePrefix: '/component',
    chapters: componentChapters,
  },
  {
    key: 'agent',
    label: { cn: 'Agent', en: 'Agent' },
    routePrefix: '/agent',
    chapters: agentChapters,
  },
];

export type Board = 'python' | 'middleware' | 'agent' | 'interview';

export interface Stage {
  id: string;       // 首页锚点
  title: string;
  goal: string;     // 走完这一段应该做到什么
  master: string[]; // 需要掌握
  slugs: string[];  // 按阅读顺序
}

export interface BoardConfig {
  key: Board;
  label: { cn: string; en: string };
  intro: string;
  stages: Stage[];
}

export const boards: BoardConfig[] = [
  {
    key: 'python',
    label: { cn: 'Python 工程', en: 'Python Engineering' },
    intro: '先把语言和运行时吃透，再用类型、库和 Web 框架把服务搭起来。Agent 的工具、接口和并发控制都建在这一层上。',
    stages: [
      {
        id: 'runtime',
        title: '语言与运行时',
        goal: '说清 Python 对象怎么存、怎么传、什么时候被回收。',
        master: [
          '可变与不可变、is 与 ==、深浅拷贝',
          '参数按对象引用传递，可变默认参数与闭包延迟绑定',
          '魔术方法、装饰器、生成器、上下文管理器、描述符',
          '引用计数、循环引用、分代 GC 与 __slots__',
        ],
        slugs: ['py-basics', 'data-model', 'memory-gc'],
      },
      {
        id: 'concurrency',
        title: '并发与网络',
        goal: '判断一段代码该用线程、进程还是协程，写出不阻塞的流式接口。',
        master: [
          'GIL 的调度方式，CPU 密集与 I/O 密集各怎么选',
          '事件循环、async/await、gather，以及阻塞事件循环的坑',
          'HTTP 状态码，SSE 与 WebSocket 的取舍',
          '流式输出、背压与超时',
        ],
        slugs: ['concurrency-gil', 'asyncio', 'network-streaming'],
      },
      {
        id: 'structure',
        title: '类型与项目结构',
        goal: '用标准库类型把模块边界写清楚，按场景挑 ORM 和缓存库。',
        master: [
          'Protocol、ABC、Literal、TypedDict、dataclass 各放在哪一层',
          '用 collections.abc 描述参数和返回值',
          'Peewee 与另外两种 ORM 的取舍',
          'cachetools 进程内缓存与 Redis 缓存怎么分工',
        ],
        slugs: ['stdlib-types', 'libraries'],
      },
      {
        id: 'web',
        title: 'Web 框架',
        goal: '用 Django、Flask、FastAPI 各写一遍同一个接口，讲清各自的请求生命周期。',
        master: [
          '中间件、请求与应用上下文、依赖注入',
          'ORM 惰性查询、N+1 与预加载、事务防超卖',
          'Pydantic 校验与 DRF 序列化',
          'async 视图、后台任务、流式响应',
        ],
        slugs: ['django', 'flask', 'fastapi'],
      },
    ],
  },
  {
    key: 'middleware',
    label: { cn: '中间件', en: 'Middleware' },
    intro: '缓存和消息队列是后端服务和 Agent 平台都绕不开的组件。重点是它们在什么条件下会丢数据、重复投递或者不一致。',
    stages: [
      {
        id: 'cache-mq',
        title: '缓存与消息',
        goal: '用 Redis 做缓存和锁，讲清 Kafka 与 RabbitMQ 各自的投递保证。',
        master: [
          'Redis 五种结构、过期、管道与事务',
          'SET NX PX 加锁、Lua 核对 token 解锁、旁路缓存的一致性',
          'Kafka 分区、副本、消费组，生产者批量与 acks，位点提交',
          'RabbitMQ 交换机路由、发布确认、手动 ack、幂等与死信',
        ],
        slugs: ['redis', 'kafka', 'rabbitmq'],
      },
    ],
  },
  {
    key: 'agent',
    label: { cn: 'Agent', en: 'Agent' },
    intro: '从模型原理到工具调用循环，再到框架和评测，是整条路线的重点。',
    stages: [
      {
        id: 'agent-basics',
        title: '模型与 Agent 原理',
        goal: '知道模型为什么会调用工具，不靠框架写出一个可控的 Agent 循环。',
        master: [
          'Transformer、注意力、解码策略与 KV Cache',
          'ReAct 循环的状态与退出条件',
          'Skills 渐进式披露与 MCP 工具接入',
          '沙盒信任边界，暂停、审批与恢复',
        ],
        slugs: ['agent-theory', 'react-agent-loop'],
      },
      {
        id: 'agent-frameworks',
        title: 'Agent 框架',
        goal: '用框架管理状态、检索和长任务，并知道每个框架替你做了什么。',
        master: [
          'LangGraph 状态图、interrupt 与 Command、检查点与线程',
          'LlamaIndex 切块、索引、Query Engine 与入库流水线',
          'Deep Agents 虚拟文件、路径权限、子代理与跨线程记忆',
        ],
        slugs: ['langgraph', 'llamaindex', 'deepagents'],
      },
      {
        id: 'agent-quality',
        title: '评测与上线',
        goal: '用数字说明一次改动让 Agent 变好还是变差。',
        master: [
          '评测分层与 harness，评测集的版本与污染',
          'RAG 检索与生成指标、记忆探针、轨迹匹配与 pass^k',
          'LLM 裁判校准与 bootstrap 发布门槛',
          'RAGAS、DeepEval、Inspect、LangSmith、promptfoo 与线上评估',
        ],
        slugs: ['agent-eval'],
      },
    ],
  },
  {
    key: 'interview',
    label: { cn: '面试', en: 'Interview' },
    intro: '前面每章末尾都附了面试题。这里集中放需要单独练的部分：算法题、手撕代码和高频真题。',
    stages: [
      {
        id: 'algorithms',
        title: '算法',
        goal: '高频数据结构题能在白板上一次写对，并说出复杂度。',
        master: [
          '链表反转与 LRU 缓存',
          '二叉树遍历、层序 BFS、最近公共祖先',
          '动态规划的状态定义、转移方程与空间压缩',
        ],
        slugs: ['linked-list', 'stack-queue', 'binary-tree', 'dynamic-programming'],
      },
      {
        id: 'coding',
        title: '手撕代码',
        goal: '常见工程题和 Agent 组件能在 30 分钟内手写出来。',
        master: [
          '计时与重试装饰器、LRU、异步限流器与并发池',
          '手写 ReAct Agent、Tool Registry 与记忆',
          'Chain-of-Thought、Self-Reflection 与三种切块',
        ],
        slugs: ['hands-on', 'agent-hands-on'],
      },
      {
        id: 'questions',
        title: '高频真题',
        goal: 'RAG 和 Agent 的常见问题能讲出原理、取舍和线上经验。',
        master: [
          'RAG 完整链路、召回与排序、检索错与生成错',
          'Function Calling 与 MCP',
          '记忆、工具失败处理、Multi-Agent、评估与迭代',
        ],
        slugs: ['rag-interview', 'agent-interview'],
      },
    ],
  },
];

const chapterBySlug = new Map(chapters.map((c) => [c.slug, c]));
const routePrefixOf = new Map(categoryConfig.map((c) => [c.key, c.routePrefix]));
const boardBySlug = new Map(
  boards.flatMap((b) => b.stages.flatMap((s) => s.slugs.map((slug) => [slug, b.key] as const))),
);

{
  const placed = boards.flatMap((b) => b.stages.flatMap((s) => s.slugs));
  const missing = chapters.filter((c) => !placed.includes(c.slug)).map((c) => c.slug);
  const unknown = placed.filter((slug) => !chapterBySlug.has(slug));
  const duplicated = placed.filter((slug, i) => placed.indexOf(slug) !== i);
  if (missing.length || unknown.length || duplicated.length) {
    throw new Error(`boards 与 chapters 不一致：缺少 ${missing} 未知 ${unknown} 重复 ${duplicated}`);
  }
}

export const chapterPath = (c: Chapter): string => `${routePrefixOf.get(c.category)}/${c.slug}`;
export const stageChapters = (s: Stage): Chapter[] => s.slugs.map((slug) => chapterBySlug.get(slug)!);
export const boardChapters = (b: BoardConfig): Chapter[] => b.stages.flatMap(stageChapters);
export const boardOfSlug = (slug: string): Board | undefined => boardBySlug.get(slug);
