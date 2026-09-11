// 数据模型章节代码:引入真实 .py 源文件,构建时用 ?raw 读取原文。
import dunder from '../code/python/data-model/dunder.py?raw';
import decorator from '../code/python/data-model/decorator.py?raw';
import generator from '../code/python/data-model/generator.py?raw';
import contextManager from '../code/python/data-model/context_manager.py?raw';
import descriptor from '../code/python/data-model/descriptor.py?raw';
import introspection from '../code/python/data-model/introspection.py?raw';
import singleton from '../code/python/data-model/singleton.py?raw';

export { dunder, decorator, generator, contextManager, descriptor, introspection, singleton };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/data-model';
