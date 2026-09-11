"""对 Agent 交付执行渲染、检查、修订和再次检查。首次使用：S7。"""

from __future__ import annotations

from typing import Any

from core.config import AppConfig
from core.context import ExecutionContext
from core.contracts import ToolCall
from core.model import OpenAIModel
from core.prompts import reflection_prompt, tool_demo_instructions
from core.runtime import ToolRegistry, execute_call, run_tool_round
from stages.common import create_initial_plan, make_task_state, run_research_agent
from tools.presentation import PresentationToolError, render_ppt
from tools.review import check_deck, review_deck_with_model


def _review_current_version(
    config: AppConfig,
    model: OpenAIModel,
    context: ExecutionContext,
) -> list[dict[str, str]]:
    """尽可能渲染当前 PPT，执行规则检查并保存报告。首次使用：S7。"""

    if context.deck is None or context.deck_version < 1:
        raise ValueError("没有可检查的 PPT")
    version = context.deck_version
    pptx_path = context.run_dir / f"deck_v{version}.pptx"
    render_dir = context.run_dir / f"slides_v{version}"
    try:
        render_result = render_ppt(
            pptx_path,
            render_dir,
            int(config.section("presentation").get("render_dpi", 144)),
        )
    except PresentationToolError as exc:
        render_result = {"rendered": False, "images": [], "warning": str(exc)}
    context.recorder.write_json(f"render_v{version}.json", render_result)
    verified_source_ids = {
        source_id
        for source_id, source in context.sources.items()
        if source.get("status") == "page_read"
    }
    issues = check_deck(context.deck, verified_source_ids, config, pptx_path)
    for issue in issues:
        issue["source"] = "rule"
    if config.section("review").get("model_review", False):
        issues.extend(review_deck_with_model(model, context.deck, config))
    # 规则 error 优先，其次规则 warning，最后模型建议；并统一重新编号。
    order = {"error": 0, "warning": 1}
    issues.sort(key=lambda item: (item.get("source") != "rule", order.get(item.get("severity"), 2)))
    for index, issue in enumerate(issues, start=1):
        issue["id"] = f"issue_{index}"
    context.recorder.write_json(f"review_v{version}.json", issues)
    context.recorder.record("deck_reviewed", version=version, issue_count=len(issues))
    return issues


def _create_revised_ppt(registry: ToolRegistry, context: ExecutionContext, round_number: int) -> None:
    """DeckPatch 成功后调用工具生成新的 PPT 版本。首次使用：S7。"""

    if context.deck is None:
        raise ValueError("DeckPatch 后没有 DeckSpec")
    result = execute_call(
        ToolCall(
            call_id=f"review_create_{round_number}",
            name="create_ppt",
            arguments={"deck": context.deck},
        ),
        registry,
        context,
        ["create_ppt"],
    )
    if not result.success:
        raise RuntimeError(result.error or "修订版 PPT 生成失败")


def run(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, Any]:
    """复用 S6 能力，然后执行有轮数上限的反馈修订。首次使用：S7。"""

    context.state = make_task_state(config)
    context.persist_state()
    create_initial_plan(config, model, context)
    outcome = run_research_agent(config, model, registry, context, enable_plan=True)
    if context.deck is None:
        return {"agent": outcome.to_dict(), "reviews": [], "message": "Agent 未交付 PPT，无法进入 Reflection"}

    reviews: list[dict[str, Any]] = []
    issues = _review_current_version(config, model, context)
    reviews.append({"version": context.deck_version, "issues": issues})
    max_rounds = int(config.section("limits")["max_review_rounds"])
    for round_number in range(1, max_rounds + 1):
        if not issues:
            break
        run_tool_round(
            model,
            registry,
            context,
            reflection_prompt(context.deck, issues),
            tool_demo_instructions(),
            ["patch_deck"],
        )
        _create_revised_ppt(registry, context, round_number)
        issues = _review_current_version(config, model, context)
        reviews.append({"version": context.deck_version, "issues": issues})
    return {"agent": outcome.to_dict(), "reviews": reviews, "final_version": context.deck_version}
