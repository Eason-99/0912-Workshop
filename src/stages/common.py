"""复用编排逻辑，同时保留各教学阶段之间的控制差异。首次使用：S3。"""

from __future__ import annotations

import json
from typing import Any

from core.config import AppConfig
from core.context import ExecutionContext
from core.contracts import (
    PlanState,
    TaskState,
    ToolCall,
    evidence_bundle_schema,
    evidence_is_comparable,
    plan_schema,
    product_selection_schema,
    validate_deck,
    validate_products,
)
from core.model import OpenAIModel
from core.prompts import (
    agent_instructions,
    deck_instructions,
    evidence_prompt,
    planning_prompt,
    selection_prompt,
    task_prompt,
)
from core.runtime import (
    AgentOutcome,
    ToolRegistry,
    execute_call,
    run_agent_loop,
)
from core.contracts import deck_schema


def make_task_state(config: AppConfig) -> TaskState:
    """仅根据可信配置创建最小初始任务状态。首次使用：S5。"""

    task = config.section("task")
    return TaskState(
        goal=task_prompt(config),
        metric_scope={
            "metric": task["primary_metric"],
            "geography": "中国大陆",
            "platform": "独立移动 App",
            "lookback_months": task["lookback_months"],
        },
    )


def _host_call(
    name: str,
    arguments: dict[str, Any],
    registry: ToolRegistry,
    context: ExecutionContext,
    sequence: int,
) -> dict[str, Any]:
    """使用显式宿主调用 ID 执行由代码选定的 Workflow 工具。首次使用：S3。"""

    result = execute_call(
        ToolCall(call_id=f"host_{sequence:03d}", name=name, arguments=arguments),
        registry,
        context,
        [name],
    )
    if not result.success:
        raise RuntimeError(result.error or f"工具失败：{name}")
    return result.data


def compact_sources(sources: dict[str, dict[str, Any]], max_text_chars: int = 2500) -> list[dict[str, Any]]:
    """压缩来源正文长度，同时保留 source_id 和 URL。首次使用：S3。"""

    compact: list[dict[str, Any]] = []
    for source in sources.values():
        item = dict(source)
        if "text" in item:
            item["text"] = str(item["text"])[:max_text_chars]
        compact.append(item)
    return compact


def build_comparability_report(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """按指标口径对定量 Evidence 分组，供图表写作前核对。首次使用：S3。"""

    groups: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for item in evidence:
        required = ("metric", "value", "unit", "period", "geography", "platform")
        missing = [field for field in required if not str(item.get(field, "")).strip()]
        if missing:
            excluded.append({"evidence_id": str(item.get("id", "")), "reason": f"缺少字段：{missing}"})
            continue
        target = next(
            (group for group in groups if evidence_is_comparable(item, group["scope"])),
            None,
        )
        if target is None:
            target = {
                "scope": {
                    "metric": item["metric"],
                    "geography": item["geography"],
                    "platform": item["platform"],
                    "unit": item["unit"],
                },
                "evidence_ids": [],
                "periods": [],
            }
            groups.append(target)
        target["evidence_ids"].append(item["id"])
        target["periods"].append(item["period"])
    for group in groups:
        group["periods"] = list(dict.fromkeys(group["periods"]))
    return {"comparable_groups": groups, "excluded": excluded}


def run_fixed_workflow(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
) -> dict[str, Any]:
    """按代码固定顺序执行搜索、读页、抽取、写作和 PPT 生成。首次使用：S3。"""

    task = config.section("task")
    cutoff = task["data_cutoff_date"]
    sequence = 1
    ranking = _host_call(
        "search_web",
        {"query": f"{cutoff} 中国 AI 助手 App 月活 MAU 排名", "date_range": "year"},
        registry,
        context,
        sequence,
    )
    sequence += 1
    selection = model.generate_structured(
        selection_prompt(config, ranking["results"]),
        "只选择符合范围且在搜索结果中出现的产品，不补造名单。",
        "product_selection",
        product_selection_schema(),
    )
    products = validate_products(
        selection["products"],
        int(task["product_count_min"]),
        int(task["product_count_max"]),
    )

    for product in products:
        for query in (
            f"{product} 月活 MAU 中国大陆 移动 App {cutoff}",
            f"{product} AI 助手 产品功能 定位 商业模式",
        ):
            search_result = _host_call(
                "search_web",
                {"query": query, "date_range": "year"},
                registry,
                context,
                sequence,
            )
            sequence += 1
            if search_result["results"]:
                candidate = search_result["results"][0]
                try:
                    _host_call(
                        "read_page",
                        {"url": candidate["url"], "source_id": candidate["source_id"]},
                        registry,
                        context,
                        sequence,
                    )
                except RuntimeError as exc:
                    context.recorder.record("workflow_gap", product=product, query=query, error=str(exc))
                sequence += 1

    read_sources = [item for item in compact_sources(context.sources) if item.get("status") == "page_read"]
    bundle = model.generate_structured(
        evidence_prompt(config, read_sources),
        "只提取原文明确支持的信息；字段缺失时留空并记录问题。",
        "evidence_bundle",
        evidence_bundle_schema(),
    )
    context.evidence = bundle["evidence"]
    context.persist_evidence()
    context.recorder.write_json("open_questions.json", bundle["open_questions"])
    comparability = (
        build_comparability_report(context.evidence)
        if task.get("require_same_scope_for_chart", True)
        else {"check_enabled": False, "comparable_groups": [], "excluded": []}
    )
    context.recorder.write_json("comparability.json", comparability)
    source_context = json.dumps(
        {
            "products": products,
            "evidence": context.evidence,
            "comparability": comparability,
            "sources": read_sources,
        },
        ensure_ascii=False,
        indent=2,
    )
    deck = model.generate_structured(
        task_prompt(config),
        deck_instructions(config, source_context),
        "deck_spec",
        deck_schema(int(task["slide_count"])),
    )
    validate_deck(deck, int(task["slide_count"]))
    delivery = _host_call("create_ppt", {"deck": deck}, registry, context, sequence)
    return {"products": products, "delivery": delivery, "open_questions": bundle["open_questions"]}


def create_initial_plan(config: AppConfig, model: OpenAIModel, context: ExecutionContext) -> PlanState:
    """调用模型生成初始显式计划并立即持久化。首次使用：S6。"""

    generated = model.generate_structured(
        planning_prompt(config),
        "计划必须短、依赖关系明确，所有步骤初始状态使用 pending。",
        "research_plan",
        plan_schema(),
    )
    plan = PlanState(items=generated["items"])
    context.plan = plan
    context.persist_plan()
    return plan


def run_research_agent(
    config: AppConfig,
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
    enable_plan: bool = False,
) -> AgentOutcome:
    """按阶段决定是否向共用 Agent Loop 注入 State 和 Plan。首次使用：S4。"""

    allowed = ["search_web", "read_page", "create_ppt"]
    if enable_plan:
        allowed.append("update_plan")

    def instructions_factory() -> str:
        """每次获得新 Observation 后重建包含最新状态的指令。首次使用：S4。"""

        state_data = context.state.to_dict() if context.state else None
        plan_data = context.plan.to_dict() if enable_plan and context.plan else None
        return agent_instructions(config, state_data, plan_data)

    return run_agent_loop(
        model,
        registry,
        context,
        task_prompt(config),
        instructions_factory,
        allowed,
    )
