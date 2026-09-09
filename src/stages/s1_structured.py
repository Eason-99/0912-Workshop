"""演示严格 `DeckSpec` 输出，但不生成 PPT 文件。首次使用：S1。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import AppConfig
from core.context import ExecutionContext
from core.contracts import deck_schema, validate_deck
from core.model import OpenAIModel
from core.prompts import deck_instructions, task_prompt

if TYPE_CHECKING:
    from core.runtime import ToolRegistry


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry | None,
    context: ExecutionContext,
) -> dict[str, str]:
    """生成、校验并保存 JSON，到此结束而不调用工具。首次使用：S1。"""

    del registry
    slide_count = int(config.section("task")["slide_count"])
    deck = model.generate_structured(
        task_prompt(config),
        deck_instructions(config),
        "deck_spec",
        deck_schema(slide_count),
    )
    validate_deck(deck, slide_count)
    path = context.recorder.write_json("deck.json", deck)
    return {"deck_path": str(path), "pptx_created": "false"}
