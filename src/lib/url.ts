// 生成带 base 前缀的站内链接（适配 GitHub Pages 项目子路径）
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  return base + '/' + path.replace(/^\//, '');
}
