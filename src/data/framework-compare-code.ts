// 三个框架章节共用的「同一接口三种写法」：同样的书店 API 分别用 Django / Flask / FastAPI 实现。
import type { CodeVariant } from './linked-list-code';
import djangoShop from '../code/framework/compare/bookshop_django.py?raw';
import flaskShop from '../code/framework/compare/bookshop_flask.py?raw';
import fastapiShop from '../code/framework/compare/bookshop_fastapi.py?raw';

export type Framework = 'django' | 'flask' | 'fastapi';

const all: Record<Framework, CodeVariant> = {
  django: { lang: 'python', label: 'Django', file: 'bookshop_django.py', code: djangoShop },
  flask: { lang: 'python', label: 'Flask', file: 'bookshop_flask.py', code: flaskShop },
  fastapi: { lang: 'python', label: 'FastAPI', file: 'bookshop_fastapi.py', code: fastapiShop },
};

/** 当前章节的框架排在第一个标签 */
export function compareVariants(current: Framework): CodeVariant[] {
  const order: Framework[] = ['django', 'flask', 'fastapi'];
  return [current, ...order.filter((f) => f !== current)].map((f) => all[f]);
}

export const COMPARE_DIR = 'src/code/framework/compare';
