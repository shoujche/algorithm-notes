"""流式客户端 —— 用 httpx 流式读取响应,逐块处理。

呼应 LLM 流式:调用方不等整段响应生成完,而是一边到达一边消费,
边收边渲染(打字机效果)。关键是用 client.stream() 而非 client.get(),
后者会把整个响应体读进内存后才返回。

运行:
    pip install httpx
    python streaming_client.py   # 需先启动 sse_server
"""
import httpx


def consume_sse(url: str = "http://127.0.0.1:8000/chat"):
    """按 SSE 帧逐行解析:识别 `data:` 行,遇到 [DONE] 结束。"""
    # timeout: 连接超时要短,但读超时(read)要给足 —— 流式响应两帧之间
    # 可能间隔很久,若 read 超时太短会误判为断连。
    timeout = httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0)
    with httpx.Client(timeout=timeout) as client:
        # stream() 返回上下文管理器,响应体不预加载
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            # iter_lines 逐行产出,底层是 chunked 解码后的文本行
            for line in resp.iter_lines():
                if not line:
                    continue  # SSE 帧之间的空行,跳过
                if line.startswith("data:"):
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        print("\n[流结束]")
                        break
                    # 逐块处理:此处直接打印,真实场景可拼接/渲染
                    print(data, end="", flush=True)


def consume_raw_chunks(url: str):
    """更底层:按字节块读取(不假设 SSE),适合下载或自定义协议。"""
    with httpx.Client() as client:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            # iter_bytes 每次拿到一个 TCP/chunk 数据块,大小不定
            for chunk in resp.iter_bytes(chunk_size=1024):
                process(chunk)


def process(chunk: bytes) -> None:
    """占位:实际按需落盘、解码或转发。消费慢会形成背压(见页面 backpressure 节)。"""
    _ = len(chunk)


if __name__ == "__main__":
    consume_sse()
