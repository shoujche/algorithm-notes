// 章节注册表：首页列表与侧边栏都从这里生成，加新章节只需在此登记 + 新建对应页面。

export type Difficulty = 'base' | 'easy' | 'mid' | 'hard';

export type Category = 'algo' | 'python';

export interface Section {
  id: string;        // 页内锚点 id
  num: string;       // 序号，如 "01"
  label: string;     // 显示名
  lc?: string;       // LeetCode 题号
}

export interface Chapter {
  slug: string;      // 路由：/topics/<slug>（algo）或 /python/<slug>（python）
  category: Category; // 归属板块：算法 / Python
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
      { id: 'reverse', num: '03', label: '链表反转', lc: '206' },
      { id: 'lru', num: '04', label: 'LRU 缓存', lc: '146' },
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
      { id: 'level-order', num: '02', label: '层序遍历', lc: '102' },
      { id: 'zigzag', num: '03', label: '锯齿形层序', lc: '103' },
      { id: 'right-view', num: '04', label: '右视图', lc: '199' },
      { id: 'lca', num: '05', label: '最近公共祖先', lc: '236' },
      { id: 'completeness', num: '06', label: '完全性检验', lc: '958' },
    ],
  },
  { slug: 'dynamic-programming', category: 'algo', num: '04', cn: '动态规划', en: 'Dynamic Programming', summary: '规划中。', ready: false },

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
  { slug: 'fastapi', category: 'python', num: 'P06', cn: 'FastAPI 工程', en: 'FastAPI', summary: '依赖注入、Pydantic、并发模型、中间件、流式响应。', ready: true,
    sections: [
      { id: 'concurrency-model', num: '01', label: '并发模型:async vs sync 路由' },
      { id: 'pydantic', num: '02', label: 'Pydantic 数据校验' },
      { id: 'di', num: '03', label: '依赖注入' },
      { id: 'middleware', num: '04', label: '中间件与生命周期' },
      { id: 'streaming', num: '05', label: '流式响应' },
    ],
  },
  { slug: 'network-streaming', category: 'python', num: 'P07', cn: '网络与流式', en: 'Network & Streaming', summary: 'HTTP 基础、SSE vs WebSocket、流式输出。', ready: true,
    sections: [
      { id: 'http', num: '01', label: 'HTTP 基础与常见状态码' },
      { id: 'sse-vs-ws', num: '02', label: 'SSE vs WebSocket' },
      { id: 'streaming', num: '03', label: '流式输出原理' },
      { id: 'backpressure', num: '04', label: '背压与超时' },
    ],
  },
  { slug: 'hands-on', category: 'python', num: 'P08', cn: '实战手撕', en: 'Hands-on Coding', summary: '手写装饰器、异步限流器、简易 tool-calling loop 等经典手撕题。', ready: true,
    sections: [
      { id: 'timer-decorator', num: '01', label: '手写计时/重试装饰器' },
      { id: 'lru', num: '02', label: '手写 LRU 缓存' },
      { id: 'rate-limiter', num: '03', label: '异步限流器' },
      { id: 'async-pool', num: '04', label: '异步并发池' },
      { id: 'tool-loop', num: '05', label: '简易 tool-calling loop' },
    ],
  },
];

export const readyChapters = chapters.filter((c) => c.ready);
export const soonChapters = chapters.filter((c) => !c.ready);

// 按板块派生
export const algoChapters = chapters.filter((c) => c.category === 'algo');
export const pythonChapters = chapters.filter((c) => c.category === 'python');

export const categoryMeta: Record<Category, { cn: string; en: string }> = {
  algo: { cn: '算法', en: 'Algorithms' },
  python: { cn: 'Python', en: 'Python' },
};
