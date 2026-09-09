// 章节注册表：首页列表与侧边栏都从这里生成，加新章节只需在此登记 + 新建对应页面。

export type Difficulty = 'base' | 'easy' | 'mid' | 'hard';

export interface Section {
  id: string;        // 页内锚点 id
  num: string;       // 序号，如 "01"
  label: string;     // 显示名
  lc?: string;       // LeetCode 题号
}

export interface Chapter {
  slug: string;      // 路由：/topics/<slug>
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
  { slug: 'stack-queue', num: '02', cn: '栈与队列', en: 'Stack & Queue', summary: '规划中。', ready: false },
  {
    slug: 'binary-tree',
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
  { slug: 'dynamic-programming', num: '04', cn: '动态规划', en: 'Dynamic Programming', summary: '规划中。', ready: false },
];

export const readyChapters = chapters.filter((c) => c.ready);
export const soonChapters = chapters.filter((c) => !c.ready);
