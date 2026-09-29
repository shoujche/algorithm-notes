"""自我反思：先出草稿，再按检查清单打分，不通过则带批评重写，限制轮数。"""

from dataclasses import dataclass


CHECKLIST = (
    "是否直接回答了问题",
    "关键数字或事实是否能被上下文支撑",
    "有没有编造工具结果",
)


@dataclass
class Draft:
    text: str
    issues: list[str]


def critic(draft: str, context: str) -> list[str]:
    issues: list[str] = []
    if len(draft.strip()) < 8:
        issues.append(CHECKLIST[0])
    if any(ch.isdigit() for ch in draft) and context and not any(
        token in context for token in draft.split() if token.isdigit()
    ):
        issues.append(CHECKLIST[1])
    if "Observation:" not in context and "根据工具返回" in draft:
        issues.append(CHECKLIST[2])
    return issues


def reflect_until_ok(writer, question: str, context: str, max_rounds: int = 3) -> str:
    feedback = ""
    for round_id in range(1, max_rounds + 1):
        draft = writer(question, context, feedback)
        issues = critic(draft, context)
        if not issues:
            return draft
        feedback = f"第{round_id}轮问题: " + "；".join(issues)
    return f"[未通过检查] {draft}"


if __name__ == "__main__":
    def writer(question: str, context: str, feedback: str) -> str:
        if feedback:
            return f"{context} 所以北京晴，5到18度。"
        return "根据工具返回，天气很好。"

    print(reflect_until_ok(writer, "北京天气", "Observation: 晴，5到18度"))
