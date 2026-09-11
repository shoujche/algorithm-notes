// asyncio 章节代码：引入真实 .py 源文件，构建时用 ?raw 读取原文。
import gatherDemo from '../code/python/asyncio/gather_demo.py?raw';
import blockingTrap from '../code/python/asyncio/blocking_trap.py?raw';

export { gatherDemo, blockingTrap };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/asyncio';
