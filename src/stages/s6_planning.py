"""在显式 State 上加入 Planning 与 Re-planning。首次使用：S6。"""

from typing import Any

from core.config import AppConfig
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.runtime import ToolRegistry
from stages.common import create_initial_plan, make_task_state, run_research_agent


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, Any]:
    """生成初始计划、开放 `update_plan` 并运行自适应循环。首次使用：S6。"""

    context.state = make_task_state(config)
    context.persist_state()
    create_initial_plan(config, model, context)
    return run_research_agent(config, model, registry, context, enable_plan=True).to_dict()
