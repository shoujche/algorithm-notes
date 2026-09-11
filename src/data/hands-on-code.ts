// 实战手撕章节代码：引入真实 .py 源文件，构建时用 ?raw 读取原文。
import decorators from '../code/python/hands-on/decorators.py?raw';
import lruCache from '../code/python/hands-on/lru_cache.py?raw';
import rateLimiter from '../code/python/hands-on/rate_limiter.py?raw';
import asyncPool from '../code/python/hands-on/async_pool.py?raw';
import toolLoop from '../code/python/hands-on/tool_loop.py?raw';

export { decorators, lruCache, rateLimiter, asyncPool, toolLoop };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/hands-on';
