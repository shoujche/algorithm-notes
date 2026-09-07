import { defineConfig } from 'astro/config';

// GitHub Pages 项目站点地址：https://<你的用户名>.github.io/algorithm-notes/
// 部署前把下面的 site 换成你的 GitHub 用户名即可（base 不用改）。
export default defineConfig({
  site: 'https://shoujche.github.io',
  base: '/algorithm-notes',
  markdown: {
    shikiConfig: { theme: 'github-dark-dimmed' },
  },
});
