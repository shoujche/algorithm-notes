"""WebSocket 端点 —— FastAPI 双向收发(echo)。

与 SSE 对比:WebSocket 是全双工(client ⇄ server 都能主动发),
握手时用 HTTP 101 Switching Protocols 升级到 ws:// 独立协议,
之后是基于帧(frame)的持久双向通道。适合聊天、协同编辑、游戏。

运行:
    pip install fastapi uvicorn websockets
    uvicorn websocket_demo:app --reload
    # 测试可用浏览器控制台:
    #   ws = new WebSocket("ws://127.0.0.1:8000/ws")
    #   ws.onmessage = e => console.log(e.data)
    #   ws.send("hello")
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


@app.websocket("/ws")
async def ws_echo(ws: WebSocket):
    """双向 echo:收到什么就回什么。

    生命周期:
      1. accept()  完成握手(HTTP 101),进入已连接状态。
      2. 循环 receive_text() 阻塞等待客户端消息。
      3. send_text() 主动回推 —— 全双工,服务端也可不等客户端就推。
      4. 客户端关闭时抛 WebSocketDisconnect,退出循环。
    """
    await ws.accept()
    await ws.send_text("已连接:发什么我回什么")
    try:
        while True:
            msg = await ws.receive_text()
            # 服务端可主动推送任意消息(与 SSE 的单向不同)
            await ws.send_text(f"echo: {msg}")
    except WebSocketDisconnect:
        # 客户端断开是正常路径,清理资源即可(此处无需额外处理)
        print("client disconnected")
