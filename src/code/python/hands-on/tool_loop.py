"""简易 tool-calling loop：手写一个最小 Agent 循环（OpenAI SDK 风格）。

呼应 Agent 章。Agent 的本质就是一个 while 循环：
  1. 把对话历史 + 可用工具描述发给 LLM
  2. LLM 要么直接回答（结束），要么要求「调用某个工具」
  3. 我们本地执行工具，把结果塞回对话历史
  4. 回到第 1 步，直到 LLM 给出最终答案

面试常让手写这个循环，考察对 tool calling 协议的理解，而非真的联网。
下面用一个假的 LLM（fake_llm）驱动，逻辑与真实 OpenAI SDK 完全同构。
"""

import json


# ============ 1. 定义工具：函数本体 + JSON Schema 描述 ============
def get_weather(city: str) -> str:
    """真正执行的工具逻辑（这里写死，实际可查 API）。"""
    data = {"北京": "晴 25°C", "上海": "多云 28°C"}
    return data.get(city, "未知城市")


# 工具注册表：名字 -> 可调用对象
TOOLS = {"get_weather": get_weather}

# 发给 LLM 的工具描述（OpenAI function calling 格式）
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询某城市的天气",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "城市名"}},
                "required": ["city"],
            },
        },
    }
]


# ============ 2. 假 LLM：模拟「先要求调工具，拿到结果后再作答」============
def fake_llm(messages):
    """返回结构模仿 OpenAI ChatCompletion 的 message 对象。

    真实场景换成：
        client.chat.completions.create(model=..., messages=messages, tools=TOOLS_SCHEMA)
    """
    # 若历史里还没有工具返回结果 -> 要求调用 get_weather
    has_tool_result = any(m["role"] == "tool" for m in messages)
    if not has_tool_result:
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city": "北京"}'},
                }
            ],
        }
    # 已经有工具结果 -> 给出最终自然语言回答
    return {"role": "assistant", "content": "北京今天天气：晴 25°C。", "tool_calls": None}


# ============ 3. 核心：Agent while 循环 ============
def run_agent(user_input: str, max_turns: int = 5) -> str:
    """手写 tool-calling loop。"""
    messages = [
        {"role": "system", "content": "你是一个天气助手，可调用工具。"},
        {"role": "user", "content": user_input},
    ]

    for turn in range(max_turns):  # max_turns 兜底，防止工具调用无限循环
        resp = fake_llm(messages)
        messages.append(resp)  # 把 LLM 的回复加入历史

        tool_calls = resp.get("tool_calls")
        if not tool_calls:
            # 没有工具调用 = LLM 给出了最终答案，退出循环
            return resp["content"]

        # 依次执行 LLM 要求的每个工具调用
        for call in tool_calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"])  # 参数是 JSON 字符串
            print(f"[tool] 调用 {name}({args})")
            result = TOOLS[name](**args)  # 本地执行工具
            # 关键：把结果以 role=tool 塞回历史，并带上 tool_call_id 关联
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": name,
                    "content": str(result),
                }
            )
        # 循环回到顶部：带着工具结果再问一次 LLM

    return "达到最大轮数仍未得到答案"


if __name__ == "__main__":
    answer = run_agent("北京天气怎么样？")
    print("最终回答:", answer)
