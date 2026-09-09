"""演示由模型控制、暂不包含显式 State 的 Action/Observation 循环。首次使用：S4。"""

from typing import Any

from core.config import AppConfig
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.runtime import ToolRegistry
from stages.common import run_research_agent


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, Any]:
    """仅依赖模型会话连续性运行最小 Agent Loop。首次使用：S4。"""

    return run_research_agent(config, model, registry, context).to_dict()
