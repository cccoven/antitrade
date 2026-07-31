"""Prompt optimization for the assistant composer."""

from i18n import t


def _demo_optimization(content: str, lang: str) -> str:
    if lang == "en":
        return (
            f"Please analyze the following request using available, verifiable data:\n\n{content}\n\n"
            "Return the key conclusion, supporting evidence, risks, and practical next steps. "
            "State clearly when required data is unavailable."
        )
    return (
        f"请使用可用且可验证的真实数据分析以下问题：\n\n{content}\n\n"
        "请依次给出核心结论、依据、主要风险和可执行的下一步；缺少必要数据时请明确说明。"
    )


async def optimize_prompt(content: str, lang: str = "zh") -> str:
    from agents import Agent, Runner
    from config import LLM_PROVIDER
    from services.agent import create_model

    text = content.strip()
    if LLM_PROVIDER == "demo":
        return _demo_optimization(text, lang)

    agent = Agent(
        name="prompt_optimizer",
        instructions=t("chat.optimize.system", lang),
        model=create_model(),
        tools=[],
    )
    result = await Runner.run(agent, input=text, max_turns=1)
    optimized = str(result.final_output or "").strip()
    return optimized or text
