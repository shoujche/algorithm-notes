"""Chain-of-Thought：把「逐步推理」写进 prompt，答案从最后一行抽取。"""

COT_PREFIX = """你是严谨的助手。先一步步思考，最后一行只写:
Answer: <最终答案>
不要在最终答案前给出结论。
"""


def build_cot_prompt(question: str, shots: list[tuple[str, str]] | None = None) -> str:
    parts = [COT_PREFIX]
    for example_q, example_reason in shots or []:
        parts.append(f"Q: {example_q}\n{example_reason}")
    parts.append(f"Q: {question}\n")
    return "\n\n".join(parts)


def parse_answer(completion: str) -> str:
    for line in reversed(completion.strip().splitlines()):
        if line.startswith("Answer:"):
            return line.split(":", 1)[1].strip()
    raise ValueError("模型没有按约定输出 Answer 行")


if __name__ == "__main__":
    shot = (
        "商店有23个苹果，卖出17个，又进5个，还剩几个？",
        "Step1: 23-17=6\nStep2: 6+5=11\nAnswer: 11",
    )
    prompt = build_cot_prompt("15的30%是多少？", shots=[shot])
    print(prompt)
    print(parse_answer("Step1: 15*0.3=4.5\nAnswer: 4.5"))
