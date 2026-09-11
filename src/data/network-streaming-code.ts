// 网络与流式章节代码：引入真实 .py 源文件，构建时用 ?raw 读取原文。
import sseServer from '../code/python/network-streaming/sse_server.py?raw';
import websocketDemo from '../code/python/network-streaming/websocket_demo.py?raw';
import streamingClient from '../code/python/network-streaming/streaming_client.py?raw';

export { sseServer, websocketDemo, streamingClient };

/** 本章源码目录（repo 相对路径），用于生成 GitHub 跳转链接 */
export const CODE_DIR = 'src/code/python/network-streaming';
