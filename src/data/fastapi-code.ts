// FastAPI 章节代码：引入真实 .py 源文件，构建时用 ?raw 读取原文。
import concurrency from '../code/python/fastapi/concurrency.py?raw';
import pydanticDemo from '../code/python/fastapi/pydantic_demo.py?raw';
import dependency from '../code/python/fastapi/dependency.py?raw';
import middleware from '../code/python/fastapi/middleware.py?raw';
import streaming from '../code/python/fastapi/streaming.py?raw';

export { concurrency, pydanticDemo, dependency, middleware, streaming };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/fastapi';
