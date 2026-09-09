"""演示两个有边界的 Tool Calling 回合，不进入 Agent Loop。首次使用：S2。"""

from core.config import AppConfig
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.prompts import task_prompt, tool_demo_instructions
from core.runtime import ToolRegistry, run_tool_round


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, str]:
    """分别演示一次搜索调用和一次 PPT 生成调用。首次使用：S2。"""

    cutoff = config.section("task")["data_cutoff_date"]
    search_summary = run_tool_round(
        model,
        registry,
        context,
        f"搜索截至 {cutoff} 的中国大陆 AI 助手 App MAU 排名候选来源。",
        tool_demo_instructions(),
        ["search_web"],
    )
    ppt_summary = run_tool_round(
        model,
        registry,
        context,
        task_prompt(config) + "\n本阶段只演示把结构化内容交给 create_ppt；不要声称完成了充分调研。",
        tool_demo_instructions(),
        ["create_ppt"],
    )
    context.recorder.write_text(
        "tool_round_summaries.md",
        f"## 搜索回合\n{search_summary}\n\n## PPT 生成回合\n{ppt_summary}\n",
    )
    return {"search_summary": search_summary, "ppt_summary": ppt_summary}
