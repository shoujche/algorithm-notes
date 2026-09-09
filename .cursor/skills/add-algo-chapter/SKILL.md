---
name: add-algo-chapter
description: >-
  Add a new chapter (or extra LeetCode problems) to the 算法手记 / Algo Notes
  Astro site (algorithm-notes repo). Covers the full workflow: register the
  chapter in topics.ts, write real runnable source files under src/code/,
  build a data-driven page with code tabs / diagrams / step animations, add
  GitHub source links, update the README source-location table, verify with a
  build + browser check, then WAIT for user review before pushing. Use when
  the user asks to add a topic, chapter, data structure, or algorithm problems
  (链表 / 二叉树 / 栈 / DP 等) to this notes site.
---

# Add a chapter to 算法手记 (Algo Notes)

Follow this to add a new chapter or new problems to the `algorithm-notes` Astro site,
consistently with the existing 链表 (linked-list) and 二叉树 (binary-tree) chapters.

## Architecture (what to know)

- **Astro static site**, deployed to GitHub Pages via `.github/workflows/deploy.yml`. Pushing to `main` auto-triggers a Pages deploy.
- **Data-driven**: `src/data/topics.ts` is the single registry. Homepage cards + each page's sidebar are generated from it.
- **Real source files**: every code block on a page is a real, editable, runnable file under `src/code/<slug>/`, imported at build time with Vite `?raw`. One source, two uses (runs locally + renders on site).
- **Per-chapter manifest**: `src/data/<slug>-code.ts` imports those files with `?raw` and exports `CODE_DIR` + `CodeVariant[]` (multi-language) + single code strings.
- **Git remote is SSH**: `git@github.com:shoujche/algorithm-notes.git`. Owner/user: `shoujche`.

## Workflow checklist

Copy and track:

```
- [ ] 1. Register chapter in src/data/topics.ts (ready:true + sections[])
- [ ] 2. Write real source files under src/code/<slug>/
- [ ] 3. Create manifest src/data/<slug>-code.ts (?raw imports + exports)
- [ ] 4. Build page src/pages/topics/<slug>.astro (hero + <section class="article"> per topic)
- [ ] 5. Add/reuse diagrams & animations in src/components/
- [ ] 6. Add component styles to src/styles/global.css ONLY if new
- [ ] 7. Update README source-location table (bullet + file table with GitHub links)
- [ ] 8. Verify: npm run build (must pass) + npm run preview + browser check
- [ ] 9. STOP — present a summary and WAIT for user review. Do NOT push.
- [ ] 10. After user approves → git add -A && commit && push origin main
```

See [reference.md](reference.md) for exact copy-paste templates (topics entry, manifest, page skeleton, README rows, animation frame model).

## Conventions

- **slug** = kebab-case (`binary-tree`, `stack-queue`). Page route is `/topics/<slug>`.
- **Language policy**: "basics" section = 4 languages via `CodeTabs` (Python, Java, Go, C++, Python first). Specific LeetCode problems = Python-only via `CodeBlock` (offer to add other languages after).
- **Source files**: clean class/functions, Chinese comments, note complexity inline (e.g. `# 头部插入 O(1)`). Each language idiomatic (Go has `package` + tabs; C++ uses includes only if needed). Whole file is shown on the site — no hidden experiment regions unless the user asks.
- **GitHub links**: use `ghBlob('src/code/<slug>/<file>')` from `src/lib/github.ts`. Pass `src=` to `CodeBlock` and `dir={CODE_DIR}` to `CodeTabs` — the filename in the code bar becomes a clickable source link (tabs update per active language).

## Component quick reference

| Component | Key props | Use for |
| --- | --- | --- |
| `CodeTabs` | `variants: CodeVariant[]`, `dir` | Multi-language code block (tabs) |
| `CodeBlock` | `code`, `lang`, `file`, `src` | Single-language code block + source link |
| `BinaryTreeDiagram` | `id`, `tree:(number\|null)[]`, `mark?`, `mark2?` | Static tree; `mark`=orange, `mark2`=teal |
| `LevelOrderAnim` | — | BFS level-order stepper (reusable pattern) |
| `Idea` | slot | Callout box for solution idea (use `<ol class="steps">`) |
| `Complexity` | `items:{l,v}[]` | Complexity strip |
| `LcBadge` | `kind: base\|easy\|mid\|hard`, `text` | Difficulty / LeetCode badge |

## SVG helpers & palette (`src/lib/svg.ts`)

- `el(tag, attrs)`, `defsArrow`, `drawNode` (rect), `drawCircleNode` (tree node), `C` (palette).
- Palette `C`: `curr`/`rev` = orange `#E8663D`, `prev` = teal `#2F9E7E`, `next` = cobalt `#3F5BD6`, `nodeDefault` `#D7DAE6`.
- Animation color code convention: **orange = current/active**, **cobalt = pending/in-queue**, **teal = done/visited**.

## Gotchas

- **Tree arrays are HEAP layout** for `BinaryTreeDiagram`: children of `i` are `2i+1`/`2i+2`; use `null` for absent nodes; NEVER place a non-null node under a `null` parent. Highlight by value (values unique per tree).
- **Unique SVG `id`** per diagram on a page (the layout script selects by id / `.tree-svg`).
- `CodeTabs`' inline `<script>` auto-binds every `.code-tabs` on the page — no per-instance wiring needed.
- `?raw` imports are already typed via `astro/client` → `vite/client`; no extra declaration needed.
- Homepage `Chapters` count is `chapters.length` (auto). New ready chapter shows up automatically.

## The review gate (important)

After step 8 passes, **stop and present a concise summary** (what was added, screenshots, build result). **Do NOT `git push` until the user explicitly approves.** Committing locally is fine; pushing (which triggers a live Pages deploy) requires user sign-off. This is the user's standing instruction.

## Verify before review

```bash
npm run build      # must exit 0
npm run preview    # then browser-check: 0 console errors, diagrams render, animation steps correct
```
Prefer Playwright for the browser check: confirm node/edge counts, step through any animation, screenshot key sections.
