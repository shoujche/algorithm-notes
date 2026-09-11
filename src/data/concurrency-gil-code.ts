// 并发/GIL 章节代码：引入真实 .py 源文件，构建时用 ?raw 读取原文。
import cpuBound from '../code/python/concurrency-gil/cpu_bound.py?raw';
import ioBound from '../code/python/concurrency-gil/io_bound.py?raw';
import raceCondition from '../code/python/concurrency-gil/race_condition.py?raw';

export { cpuBound, ioBound, raceCondition };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/concurrency-gil';
