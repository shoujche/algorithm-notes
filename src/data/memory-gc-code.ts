// 内存管理与 GC 章节代码：引入真实 .py 源文件，构建时用 ?raw 读取原文。
import refcount from '../code/python/memory-gc/refcount.py?raw';
import cycle from '../code/python/memory-gc/cycle.py?raw';
import weakrefDemo from '../code/python/memory-gc/weakref_demo.py?raw';
import slotsDemo from '../code/python/memory-gc/slots_demo.py?raw';

export { refcount, cycle, weakrefDemo, slotsDemo };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/memory-gc';
