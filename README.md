# 算法手记 · Algo Notes

> 图解数据结构与算法，带分步动画的 LeetCode 题解
> Visual data structures & algorithms notes with animated LeetCode solutions.

从零开始记录数据结构与算法的学习，用可交互的分步动画拆解每一道经典题。基于 [Astro](https://astro.build) 构建，纯静态，部署在 GitHub Pages。

## 本地开发

```bash
npm install      # 安装依赖
npm run dev      # 启动开发服务器 → http://localhost:4321/algorithm-notes
npm run build    # 构建静态产物到 dist/
npm run preview  # 本地预览构建结果
```

## 项目结构

```
src/
├─ data/topics.ts          # 章节注册表（首页 + 侧边栏统一数据源）
├─ layouts/BaseLayout.astro # 页面外壳（头部 / 字体 / 页脚）
├─ components/              # 组件
│  ├─ SiteHeader / Sidebar  # 顶栏、侧边栏
│  ├─ CodeBlock / Idea …    # 代码块、思路、复杂度、题号徽标
│  └─ *Anim / *Diagram      # 链表反转、LRU 等 SVG 动画
├─ pages/
│  ├─ index.astro           # 首页（章节目录）
│  └─ topics/linked-list.astro  # 链表章节
└─ styles/global.css        # 设计令牌与全部样式
```

### 新增一个章节

1. 在 `src/data/topics.ts` 的 `chapters` 里登记（把 `ready` 设为 `true`）。
2. 新建 `src/pages/topics/<slug>.astro`，复用 `BaseLayout` + 现有组件。
3. 需要新动画时，在 `src/components/` 里新增一个 `*Anim.astro`。

## 部署到 GitHub Pages

1. 在 GitHub 新建仓库 **`algorithm-notes`**，把本地代码推上去。
2. 打开 `astro.config.mjs`，把 `site` 改成 `https://<你的用户名>.github.io`（`base` 保持 `/algorithm-notes`）。
3. 仓库 **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**。
4. 推送到 `main` 分支即自动构建部署，站点地址：
   `https://<你的用户名>.github.io/algorithm-notes/`

## 建议的 GitHub Topics（提升检索）

`algorithms` `data-structures` `leetcode` `dsa` `algorithm-visualization`
`animation` `interview` `notes` `python` `learning`
