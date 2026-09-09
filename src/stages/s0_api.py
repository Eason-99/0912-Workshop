"""演示不含工具和 Schema 的单次自由文本模型调用。首次使用：S0。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import AppConfig
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.prompts import task_prompt

if TYPE_CHECKING:
    from core.runtime import ToolRegistry


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry | None,
    context: ExecutionContext,
) -> dict[str, str]:
    """生成并保存五页文字草稿，同时明确没有实时检索。首次使用：S0。"""

    del registry
    draft = model.generate_text(
        task_prompt(config),
        "直接给出五页文字草稿。当前没有联网工具，必须明确说明未执行实时检索，不得编造最新数字。",
    )
    path = context.recorder.write_text("draft.md", draft)
    return {"draft_path": str(path)}
