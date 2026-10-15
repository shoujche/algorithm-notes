"""流式响应(StreamingResponse):边生成边发送,呼应 LLM 的流式输出。

普通 Response:服务端把整个结果算完、拼成完整 body,一次性发给客户端。
             客户端要等全部就绪才能看到第一个字节。

StreamingResponse:服务端用一个生成器「产出一块、发一块」,客户端可以边收边显示。
             这正是 ChatGPT 那种「逐字蹦出来」的底层机制 —— 首字节延迟低、体验好、
             且服务端不必把整段长文本都堆在内存里。
"""

import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


# ---------------------------------------------------------------------------
# 1) 基础流式:async generator 逐块 yield
# ---------------------------------------------------------------------------
async def fake_llm_tokens():
    """模拟 LLM 逐 token 生成:每产出一个词就 yield 出去。"""
    tokens = ["FastAPI ", "的 ", "流式 ", "响应 ", "很 ", "适合 ", "LLM。"]
    for tok in tokens:
        await asyncio.sleep(0.2)  # 模拟模型推理耗时;await 期间不阻塞其他请求
        yield tok  # 产出一块,FastAPI 立即把它发给客户端


@app.get("/stream")
async def stream():
    # media_type 用 text/plain,客户端会持续收到文本片段。
    return StreamingResponse(fake_llm_tokens(), media_type="text/plain")


# ---------------------------------------------------------------------------
# 2) SSE(Server-Sent Events)格式:前端用 EventSource 天然支持
# ---------------------------------------------------------------------------
async def sse_events():
    """SSE 协议要求每条消息形如:`data: <内容>\\n\\n`(两个换行结尾)。"""
    for i in range(5):
        await asyncio.sleep(0.5)
        # 每条事件按 SSE 帧格式产出;浏览器 EventSource 会自动解析成 message 事件。
        yield f"data: 第 {i} 条消息\n\n"
    # 自定义结束信号,前端收到后主动关闭连接(SSE 没有内建的「完成」帧)。
    yield "data: [DONE]\n\n"


@app.get("/sse")
async def sse():
    return StreamingResponse(
        sse_events(),
        media_type="text/event-stream",  # SSE 的标准 MIME 类型
        headers={
            "Cache-Control": "no-cache",   # 禁止缓存,保证实时
            "Connection": "keep-alive",    # 保持长连接
        },
    )


# ---------------------------------------------------------------------------
# StreamingResponse vs 普通 Response:
#   维度          普通 Response         StreamingResponse
#   -----------   -------------------   --------------------------
#   发送时机      算完一次性发          边算边发,逐块推送
#   首字节延迟    高(要等全部)        低(第一块就发)
#   内存占用      要容纳整个 body       只需容纳当前块
#   适用场景      小型 JSON、普通页面   LLM 输出、大文件下载、实时日志
#
# 面试点:LLM 流式输出为什么用 SSE 而不用 WebSocket?
#   —— LLM 场景是「服务端单向持续推 token」,SSE 单向、基于 HTTP、自动重连、
#      实现简单,正好够用;WebSocket 是双向全双工,对纯下行场景是杀鸡用牛刀。
# ---------------------------------------------------------------------------
