import type { Chapter } from '../data/topics';

/** 力扣中文站原题。slug 与 leetcode.com/problems 相同。 */
export function leetcodeProblemUrl(slug: string): string {
  return `https://leetcode.cn/problems/${slug}/`;
}

export function sectionProblemUrl(chapter: Chapter, sectionId: string): string | undefined {
  const slug = chapter.sections?.find((section) => section.id === sectionId)?.lcSlug;
  return slug ? leetcodeProblemUrl(slug) : undefined;
}
