"""SSE(Server-Sent Events)服务端 —— 用 FastAPI 输出 text/event-stream。

场景:模拟 LLM 逐 token 流式返回。SSE 是单向(服务端 → 客户端)推送,
基于普通 HTTP 长连接,浏览器原生 EventSource 支持,断线自动重连。

运行:
    pip install fastapi uvicorn
    uvicorn sse_server:app --reload
    # 测试:curl -N http://127.0.0.1:8000/chat
"""
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


async def token_stream():
    """异步生成器:边算边发,每次 yield 一个 SSE 事件帧。

    SSE 帧格式(关键):
      - 以 `data: ` 开头,内容后跟两个换行 `\\n\\n` 表示一帧结束。
      - 可选 `event:`(事件名)、`id:`(用于断线重连的 Last-Event-ID)、
        `retry:`(重连间隔毫秒)。
    """
    tokens = ["流式", "输出", "让", "首字节", "延迟", "更", "低", "。"]
    for i, tok in enumerate(tokens):
        # 模拟模型生成每个 token 需要的时间
        await asyncio.sleep(0.3)
        # 每帧一个 token;真实 LLM 网关通常发 JSON,如 OpenAI 的 data: {...}
        yield f"id: {i}\ndata: {tok}\n\n"
    # 约定的结束标志(仿 OpenAI 的 `data: [DONE]`)。
    # 注意:SSE 协议本身没有"结束"概念,靠应用层约定或服务端关闭连接。
    yield "data: [DONE]\n\n"


@app.get("/chat")
async def chat():
    """返回 StreamingResponse,媒体类型必须是 text/event-stream。

    额外响应头:
      - Cache-Control: no-cache  避免代理缓存流。
      - X-Accel-Buffering: no    关闭 Nginx 缓冲,否则流会被攒起来一次性下发。
    """
    return StreamingResponse(
        token_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
