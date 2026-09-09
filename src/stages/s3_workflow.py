"""演示由代码控制的固定调研与 PPT Workflow。首次使用：S3。"""

from typing import Any

from core.config import AppConfig
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.runtime import ToolRegistry
from stages.common import run_fixed_workflow


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, Any]:
    """执行不根据 Observation 临时改变路径的固定流程。首次使用：S3。"""

    return run_fixed_workflow(config, model, registry, context)
