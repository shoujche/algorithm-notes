# Python + Agent 面试题材料 — 设计文档

> 状态:设计已定稿(融合进 algorithm-notes Astro 站点)
> 目标:把 Python 基础 + Agent 方向的面试知识,作为一个新「板块」融入现有算法手记站点,与算法章节风格统一。

## 1. 交付形式(已更新:融入 Astro 站点)

- **载体**:融入现有 `algorithm-notes`(Astro 静态站),**不再是独立 HTML**。
- **顶层双板块**:站点从「算法单一主题」升级为两大板块 —— **算法(Algorithms)** / **Python 知识(Python & Agent)**。
- **风格统一**:复用现有组件与视觉(`LcBadge`/`Idea`/`Complexity`/`CodeTabs`/`CodeBlock` + 动画/图组件),Shiki 代码高亮,`github-dark-dimmed` 主题。
- **图**:沿用站点现有的图/动画组件风格;新增流程类图(事件循环、GIL 调度、Agent 流程)用内联 SVG 或 Mermaid(见融合方案 §9)。

## 2. 难度与受众

- **分层(D)**:每个主题从「基础八股」→「原理/场景」→「进阶/权衡」逐层递进。
- 每题标注难度标签:🟢 基础 / 🟡 中级 / 🔴 高级。

## 3. 主题范围(全选)

| # | 模块 | 覆盖要点 |
|---|------|----------|
| A | Python 语言基础 | 数据类型、可变/不可变、is vs ==、深浅拷贝、参数传递 |
| B | 数据模型/高级特性 | 魔术方法、装饰器、生成器/迭代器、上下文管理器、描述符 |
| C | 内存管理/GC | 引用计数、循环引用、分代 GC、`__slots__` |
| D | 并发编程 / GIL | GIL 原理与调度、线程/进程/协程对比与选型 |
| E | asyncio 深入 | 事件循环、协程调度、async/await 原理、常见坑 |
| F | FastAPI 工程 | 依赖注入、Pydantic、并发模型(async vs sync 路由)、中间件、流式响应 |
| G | 网络/HTTP/WebSocket | HTTP 基础、SSE vs WebSocket、流式输出 |
| H | Agent 基础 | LLM 调用、Tool Calling、RAG、上下文管理、流式、多轮 |

## 4. 每题结构

- 标题 + 难度标签
- 问题描述(面试官口吻)
- 参考答案(要点 + 展开讲解)
- 代码示例(必要时)
- 架构图 / 流程图(必要时,Mermaid)
- 「面试官追问」栏(考察深度)

## 5. 规模与分布(已定)

- **规模**:全面版,每模块 6-8 题,共 60+ 题。
- **权重**:8 模块平均分布(基础模块不从简,同样给足题)。
- **手撕代码专区**:独立板块「实战手撕」,5-6 道经典题(手写装饰器、异步限流器、简易 tool-calling loop、生成器实现协程、LRU 缓存、并发爬虫等)。
- **语言**:全中文,关键术语保留英文原词(GIL、event loop、coroutine、tool calling 等)。

## 6. 表现层与代码风格(已定)

- **Agent 代码风格**:OpenAI SDK 风格(`client.chat.completions.create` + `tools`),事实标准,面试通用性最好。tool calling loop、流式、RAG 均以此为准。
- **页面结构**:左侧固定侧边栏目录(可跳转各模块 + 显示题量),主区按模块罗列;每题「参考答案 / 讲解」可折叠;顶部搜索/难度筛选(可选增强)。
- **视觉**:代码高亮、Mermaid 图内联渲染、难度标签色块、支持浅色/深色主题。

## 7. 模块清单与产出顺序

A 语言基础 → B 数据模型/高级特性 → C 内存/GC → D 并发/GIL → E asyncio → F FastAPI → G 网络/流式 → H Agent 基础 → 实战手撕专区。

每模块 6-8 题,难度分层(🟢🟡🔴),重点模块(D/E/F/H)配架构图。

---

## 8. 融合方案:接入 algorithm-notes(已定)

### 8.1 顶层板块建模(Q1 → A)

给 `src/data/topics.ts` 的 `Chapter` 增加一个字段:

```ts
export type Category = 'algo' | 'python';

export interface Chapter {
  slug: string;
  category: Category;   // 新增:归属板块
  num: string;
  cn: string;
  en: string;
  summary: string;
  sections?: Section[];
  ready: boolean;
}
```

- 现有 4 个算法章节补 `category: 'algo'`。
- 新增 Python 章节标 `category: 'python'`,序号独立编号(P01…)。
- 派生:`algoChapters = chapters.filter(c => c.category==='algo')`、`pythonChapters = ...==='python'`。

### 8.2 顶部导航(Q2 → A + 高亮)

`SiteHeader.astro` 增加一级导航入口:**算法** / **Python 面试**,当前板块高亮。
- 算法 → `/`(或 `/#algo`)
- Python → `/python`(新首页)或首页 Python 区块锚点。

### 8.3 首页分区

`index.astro` 从单一 `chapters.map` 改为**按板块分组**渲染两个区块:
- 「算法 · Algorithms」区块 → `algoChapters`
- 「Python & Agent」区块 → `pythonChapters`
- Hero 的统计数字(Chapters 数等)相应更新。

### 8.4 侧边栏分组

`Sidebar.astro` 的「全部章节」列表按 `category` 分两组标题展示(算法 / Python),当前章节所在组默认展开。

## 9. Python 板块页面形态(Q3 → A,Q4 → C)

- **每个模块 = 一个 chapter**,路由 `/python/<slug>`(新建 `src/pages/python/` 目录),共 8-9 个 Python 章节 + 1 个「实战手撕」章节。
- 页面沿用算法章范式:Hero → `section.article` 小节(问题→答案→代码→图)→ 复用 `LcBadge`/`Complexity`/`CodeTabs`。
- **风格 = 知识讲解为主(Q4→C)**:每小节讲清知识点;小节末尾附「面试追问」小框,复用 `Idea` 组件样式(或新建 `Interview` 组件),放追问点 + 简答。
- 代码放 `src/code/python/<slug>/*.py`,沿用现有 `CodeTabs` + GitHub 链接机制。

### 9.1 Python 章节清单(category: 'python')

| slug | 序号 | 中文 | 英文 |
|------|------|------|------|
| py-basics | P01 | 语言基础 | Language Basics |
| data-model | P02 | 数据模型与高级特性 | Data Model |
| memory-gc | P03 | 内存管理与 GC | Memory & GC |
| concurrency-gil | P04 | 并发与 GIL | Concurrency & GIL |
| asyncio | P05 | asyncio 深入 | Asyncio |
| fastapi | P06 | FastAPI 工程 | FastAPI |
| network-streaming | P07 | 网络与流式 | Network & Streaming |
| agent-basics | P08 | Agent 基础 | Agent Basics |
| hands-on | P09 | 实战手撕 | Hands-on Coding |

## 10. 目录改动清单

```
src/
  data/
    topics.ts              # 加 category 字段 + 派生数组
    python-*-code.ts        # 各 Python 章的代码数据(按需)
  pages/
    index.astro            # 改为按板块分组
    python/                # 新建:Python 板块页面
      py-basics.astro
      concurrency-gil.astro
      ...
  code/
    python/<slug>/*.py     # Python 示例代码
  components/
    SiteHeader.astro       # 加一级导航
    Sidebar.astro          # 按 category 分组
    Interview.astro        # 新建(可选):面试追问框
```

## 11. 产出顺序(分批,便于评审)

1. **地基**:改 `topics.ts`(category)、`index.astro`(分区)、`SiteHeader`、`Sidebar` —— 先让双板块骨架跑起来(Python 章可先占位 `ready:false`)。
2. **重点模块优先**:并发/GIL(P04)→ asyncio(P05)→ FastAPI(P06)→ Agent(P08)。
3. **基础模块**:P01 / P02 / P03 / P07。
4. **实战手撕**:P09。

---
> 设计已定稿。下一步:先做 §11 第 1 步(双板块地基),再逐章产出内容。
