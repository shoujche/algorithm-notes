// Django 章节代码：每个文件都是单文件可运行脚本（settings.configure + 内存 SQLite）。
import requestCycle from '../code/framework/django/request_cycle.py?raw';
import ormQueries from '../code/framework/django/orm_queries.py?raw';
import nPlusOne from '../code/framework/django/n_plus_one.py?raw';
import transactionStock from '../code/framework/django/transaction_stock.py?raw';
import drfApi from '../code/framework/django/drf_api.py?raw';
import asyncTasks from '../code/framework/django/async_tasks.py?raw';

export { requestCycle, ormQueries, nPlusOne, transactionStock, drfApi, asyncTasks };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/framework/django';
