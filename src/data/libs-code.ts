// 常用第三方库：Peewee、cachetools、Django / Flask / Redis 缓存。
import peeweeOrm from '../code/framework/libs/peewee_orm.py?raw';
import memoryCache from '../code/framework/libs/memory_cache.py?raw';
import sharedCache from '../code/framework/libs/shared_cache.py?raw';

export { peeweeOrm, memoryCache, sharedCache };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/framework/libs';
