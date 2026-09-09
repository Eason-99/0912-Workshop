"""为 Agent Loop 加入由 runtime 维护的显式 `TaskState`。首次使用：S5。"""

from typing import Any

from core.config import AppConfig
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.runtime import ToolRegistry
from stages.common import make_task_state, run_research_agent


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, Any]:
    """启用显式 State，在循环前后持续保存可信执行事实。首次使用：S5。"""

    context.state = make_task_state(config)
    context.persist_state()
    return run_research_agent(config, model, registry, context).to_dict()
