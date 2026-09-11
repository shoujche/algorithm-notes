// 生成指向本仓库 GitHub 源码的链接。
// 页面上的每个代码块都用它跳转到对应源文件所在位置。

const REPO = 'https://github.com/shoujche/algorithm-notes';
const BRANCH = 'main';

/** repo 相对路径（如 `src/code/linked-list/linked_list.py`）→ GitHub 单文件链接 */
export function ghBlob(repoPath: string): string {
  return `${REPO}/blob/${BRANCH}/${repoPath}`;
}

/** repo 相对路径（如 `src/code/linked-list`）→ GitHub 目录链接 */
export function ghTree(repoPath: string): string {
  return `${REPO}/tree/${BRANCH}/${repoPath}`;
}

/** 新建 issue 链接，可带预填标题 */
export function ghNewIssue(title?: string): string {
  const q = title ? `?title=${encodeURIComponent(title)}` : '';
  return `${REPO}/issues/new${q}`;
}

/** 仓库首页（用于「提 PR / fork」入口） */
export const ghRepo = REPO;
