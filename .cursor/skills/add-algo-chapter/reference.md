# Templates & details

Copy-paste templates for adding a chapter. Replace `<slug>`, `<Cn>`, `<En>`, numbers, and problem specifics.

## 1. Register the chapter — `src/data/topics.ts`

Flip `ready` to `true` and add `sections`. `id` is the in-page anchor; `lc` shows the LeetCode number in the sidebar.

```ts
{
  slug: 'binary-tree',
  num: '03',
  cn: '二叉树',
  en: 'Binary Tree',
  summary: '一句话简介，会显示在首页卡片。',
  ready: true,
  sections: [
    { id: 'basics', num: '01', label: '构建与遍历' },
    { id: 'level-order', num: '02', label: '层序遍历', lc: '102' },
    // ...
  ],
},
```

## 2. Real source files — `src/code/<slug>/`

- Basics (4 languages): `tree_node.py`, `TreeNode.java`, `tree_node.go`, `tree_node.cpp`.
- Each problem (Python): `snake_case.py` (e.g. `level_order.py`).
- Clean, idiomatic, Chinese comments, inline complexity. Whole file is displayed.

## 3. Manifest — `src/data/<slug>-code.ts`

Reuse the `CodeVariant` type from `linked-list-code.ts`.

```ts
import type { CodeVariant } from './linked-list-code';

import basicsPy from '../code/binary-tree/tree_node.py?raw';
import basicsJava from '../code/binary-tree/TreeNode.java?raw';
import basicsGo from '../code/binary-tree/tree_node.go?raw';
import basicsCpp from '../code/binary-tree/tree_node.cpp?raw';

import levelOrderCode from '../code/binary-tree/level_order.py?raw';
// ... more problem imports

export { levelOrderCode /*, ... */ };

export const CODE_DIR = 'src/code/binary-tree';

export const basicsVariants: CodeVariant[] = [
  { lang: 'python', label: 'Python', file: 'tree_node.py', code: basicsPy },
  { lang: 'java', label: 'Java', file: 'TreeNode.java', code: basicsJava },
  { lang: 'go', label: 'Go', file: 'tree_node.go', code: basicsGo },
  { lang: 'cpp', label: 'C++', file: 'tree_node.cpp', code: basicsCpp },
];
```

## 4. Page skeleton — `src/pages/topics/<slug>.astro`

Frontmatter imports:

```astro
---
import BaseLayout from '../../layouts/BaseLayout.astro';
import Sidebar from '../../components/Sidebar.astro';
import LcBadge from '../../components/LcBadge.astro';
import Idea from '../../components/Idea.astro';
import Complexity from '../../components/Complexity.astro';
import CodeBlock from '../../components/CodeBlock.astro';
import CodeTabs from '../../components/CodeTabs.astro';
// import diagrams/animations as needed
import { chapters } from '../../data/topics';
import { basicsVariants, levelOrderCode, CODE_DIR } from '../../data/binary-tree-code';
import { ghBlob } from '../../lib/github';

const chapter = chapters.find((c) => c.slug === 'binary-tree')!;
---
```

Body: hero + one `<section>` per topic.

```astro
<BaseLayout title="二叉树 Binary Tree · 算法手记">
  <div class="layout">
    <Sidebar chapterCn={chapter.cn} chapterEn={chapter.en} currentSlug={chapter.slug} sections={chapter.sections} />
    <main>
      <div class="hero">
        <span class="eyebrow">算法手记 / 第 {chapter.num} 章 · 二叉树 Binary Tree</span>
        <h2>标题：可用 <em>强调词</em><br />副标题</h2>
        <p>章节导语。</p>
        <div class="meta">
          <div><span class="n">06</span><span class="l">Topics</span></div>
          <div><span class="n">5</span><span class="l">LeetCode</span></div>
          <div><span class="n">4</span><span class="l">Languages</span></div>
          <div><span class="n">动画</span><span class="l">Interactive</span></div>
        </div>
      </div>

      <!-- multi-language basics section -->
      <section class="article" id="basics">
        <div class="art-head"><span class="num">01</span><LcBadge kind="base" text="基础 · Basics" /></div>
        <h3>标题 Title</h3>
        <p class="lead">一句话概述。行内代码用 <kbd>val</kbd>。</p>
        <!-- <Diagram /> optional -->
        <Idea>
          <ol class="steps"><li>要点一</li><li>要点二</li></ol>
        </Idea>
        <CodeTabs variants={basicsVariants} dir={CODE_DIR} />
        <Complexity items={[{ l: '时间', v: 'O(n)' }, { l: '空间', v: 'O(h)' }]} />
      </section>

      <!-- single-language problem section -->
      <section class="article" id="level-order">
        <div class="art-head"><span class="num">02</span><LcBadge kind="mid" text="LeetCode 102 · Medium" /></div>
        <h3>题目名 Level Order</h3>
        <p class="lead">题面。</p>
        <h4 class="sub">解题思路 · 一句话</h4>
        <Idea>思路，配 <ol class="steps">…</ol></Idea>
        <!-- <SomeAnim /> optional -->
        <CodeBlock code={levelOrderCode} lang="python" file="level_order.py"
          src={ghBlob(`${CODE_DIR}/level_order.py`)} />
        <Complexity items={[{ l: '时间', v: 'O(n)' }, { l: '空间', v: 'O(n)' }]} />
      </section>
    </main>
  </div>
</BaseLayout>
```

## 5. README source-location table

Add under the existing "## 源码位置" section (in the repo root `README.md`):

```md
- <Cn>章节全部源码：[`src/code/<slug>/`](https://github.com/shoujche/algorithm-notes/tree/main/src/code/<slug>)

| 文件 | 说明 |
| --- | --- |
| [`file.py`](https://github.com/shoujche/algorithm-notes/blob/main/src/code/<slug>/file.py) | 说明（LeetCode xxx） |
```

## 6. Static tree diagram usage (`BinaryTreeDiagram`)

Heap-layout arrays (children of `i` = `2i+1`/`2i+2`, `null` = absent):

```astro
<BinaryTreeDiagram id="tree-basics" tree={[1,2,3,4,5,6,7]} />
<BinaryTreeDiagram id="tree-lca" tree={[3,5,1,6,2,0,8]} mark={[6,2]} mark2={[5]} />
```

`mark` = orange (targets / visible), `mark2` = teal (e.g. the answer node).

## 7. Step-animation frame model (for new `*Anim.astro`)

Pattern used by `ReverseAnim` and `LevelOrderAnim`:

1. Define the fixed input (array / heap tree) at top of the client `<script>`.
2. `buildFrames()` → `Frame[]`; each frame is a full snapshot (state vars, caption HTML). Deep-copy mutable state per frame.
3. `render()` redraws SVG + panel from `frames[idx]`; disables prev/next at bounds; updates progress `fill` + `count`.
4. Controls: `重置 / ‹上一步 / ▶播放 / 下一步›` (reuse `.btn`, `.stepbar`, `.progress`, `.caption` classes).
5. Caption uses `<span class="k">标签</span>说明 <b>值</b>`.

Reuse existing CSS: `.stage`, `.grid`, `.svg-wrap`, `.panel`, `.controls`, `.btn`, `.stepbar`, `.caption`, `.node-val`, `.edge`. Add new classes to `global.css` only for genuinely new UI (e.g. BFS queue chips: `.chip`, `.lvl-row`).

## 8. Deploy notes

- Remote is SSH (`git@github.com:shoujche/algorithm-notes.git`). If a push is rejected as non-fast-forward, `git stash` any unrelated local edits, `git pull --rebase origin main`, push, then pop.
- Push to `main` triggers the GitHub Actions Pages deploy. Live site: `https://shoujche.github.io/algorithm-notes/`.
- **Only push after the user has reviewed and approved.**
