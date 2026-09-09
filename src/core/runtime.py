"""实现工具注册/执行、运行上下文以及最小 Agent Loop。首次使用：S2。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import time
from typing import Any, Callable

from core.config import AppConfig
from core.context import ExecutionContext
from core.contracts import (
    ToolCall,
    ToolResult,
    deck_patch_schema,
    deck_schema,
    plan_schema,
    validate_deck,
)
from core.model import ModelError, OpenAIModel
from core.recorder import Recorder
from tools.presentation import create_ppt, patch_deck
from tools.research import read_page, search_web


@dataclass
class ToolDefinition:
    """把模型可见的工具 Schema 与本地处理函数绑定。首次使用：S2。"""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], "ExecutionContext"], dict[str, Any]]

    def openai_schema(self) -> dict[str, Any]:
        """将本地工具定义转换为 Responses API 工具 Schema。首次使用：S2。"""

        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }


class ToolRegistry:
    """集中注册、按阶段暴露并执行允许使用的工具。首次使用：S2。"""

    def __init__(self) -> None:
        """创建空工具注册表。首次使用：S2。"""

        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        """注册一个名称唯一的工具定义。首次使用：S2。"""

        if definition.name in self._tools:
            raise ValueError(f"工具重复注册：{definition.name}")
        self._tools[definition.name] = definition

    def schemas(self, names: list[str]) -> list[dict[str, Any]]:
        """返回当前阶段允许暴露给模型的工具 Schema 子集。首次使用：S2。"""

        missing = [name for name in names if name not in self._tools]
        if missing:
            raise ValueError(f"工具未注册：{missing}")
        return [self._tools[name].openai_schema() for name in names]

    def execute(self, call: ToolCall, context: "ExecutionContext") -> ToolResult:
        """校验参数并执行一次工具，把异常统一转换为 `ToolResult`。首次使用：S2。"""

        definition = self._tools.get(call.name)
        if definition is None:
            return ToolResult(call.call_id, call.name, False, error="工具不存在或未开放")
        try:
            _validate_schema_value(call.arguments, definition.parameters, call.name)
            data = definition.handler(call.arguments, context)
            return ToolResult(call.call_id, call.name, True, data=data)
        except Exception as exc:  # 工具失败必须转换为模型可见的 Observation。
            return ToolResult(call.call_id, call.name, False, error=str(exc))


@dataclass(frozen=True)
class AgentOutcome:
    """汇总 Agent Loop 的结束状态、步数和交付路径。首次使用：S4。"""

    status: str
    steps: int
    final_text: str
    deck_path: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """将 Agent 结束结果转换为可写入 JSON 的字典。首次使用：S4。"""

        return {
            "status": self.status,
            "steps": self.steps,
            "final_text": self.final_text,
            "deck_path": self.deck_path,
            "error": self.error,
        }


def _object_schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    """为工具参数构造不允许额外字段的 object Schema。首次使用：S2。"""

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _validate_schema_value(value: Any, schema: dict[str, Any], path: str) -> None:
    """递归校验 Demo 工具实际使用的严格 JSON Schema 子集。首次使用：S2。"""

    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path} 必须是 object")
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"{path} 缺少字段：{missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ValueError(f"{path} 包含未知字段：{extras}")
        for key, item in value.items():
            if key in properties:
                _validate_schema_value(item, properties[key], f"{path}.{key}")
    elif expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path} 必须是 array")
        if len(value) < int(schema.get("minItems", 0)):
            raise ValueError(f"{path} 数量不足")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            raise ValueError(f"{path} 数量过多")
        for index, item in enumerate(value):
            _validate_schema_value(item, schema.get("items", {}), f"{path}[{index}]")
    elif expected == "string" and not isinstance(value, str):
        raise ValueError(f"{path} 必须是 string")
    elif expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        raise ValueError(f"{path} 必须是 integer")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} 必须是 {schema['enum']} 之一")


def _search_handler(arguments: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
    """执行网页搜索，并把候选结果加入来源集合。首次使用：S2。"""

    result = search_web(arguments["query"], context.config, arguments.get("date_range", ""))
    for source in result["results"]:
        context.sources[source["source_id"]] = source
    context.persist_sources()
    return result


def _read_handler(arguments: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
    """读取候选网页，并将对应来源升级为 `page_read` 状态。首次使用：S3。"""

    result = read_page(arguments["url"], context.config, arguments.get("source_id", ""))
    context.sources[result["source_id"]] = result
    context.persist_sources()
    return result


def _create_ppt_handler(arguments: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
    """校验来源后生成版本化 PPT，并保存当前 `DeckSpec`。首次使用：S2。"""

    deck = arguments["deck"]
    validate_deck(deck, int(context.config.section("task")["slide_count"]))
    referenced = {
        source_id
        for slide in deck.get("slides", [])
        for source_id in slide.get("source_ids", [])
    }
    unread = sorted(
        source_id
        for source_id in referenced
        if context.sources.get(source_id, {}).get("status") != "page_read"
    )
    if unread:
        raise ValueError(f"PPT 引用了尚未 read_page 核对的来源：{unread}")
    next_version = context.deck_version + 1
    json_name = f"deck_v{next_version}.json"
    pptx_name = f"deck_v{next_version}.pptx"
    context.recorder.write_json(json_name, deck)
    result = create_ppt(deck, context.run_dir / pptx_name, context.config)
    stable_name = str(context.config.section("presentation")["output_filename"])
    shutil.copyfile(context.run_dir / pptx_name, context.run_dir / stable_name)
    result["stable_pptx_path"] = str(context.run_dir / stable_name)
    context.deck_version = next_version
    context.deck = deck
    if context.state is not None:
        context.state.current_deck = pptx_name
        context.persist_state()
    context.recorder.record("presentation_created", version=context.deck_version, **result)
    return result


def _update_plan_handler(arguments: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
    """应用模型提出的新计划，并记录明确的调整依据。首次使用：S6。"""

    if context.plan is None:
        raise ValueError("当前阶段未启用 Plan")
    context.plan.replace(arguments["items"], arguments["reason"])
    context.persist_plan()
    return {"revision": context.plan.revision, "change_reason": context.plan.change_reason}


def _patch_deck_handler(arguments: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
    """把模型请求的页面替换应用到当前 `DeckSpec`。首次使用：S7。"""

    if context.deck is None:
        raise ValueError("当前没有可修订的 DeckSpec")
    context.deck = patch_deck(context.deck, arguments)
    context.recorder.write_json(f"deck_patch_{context.deck_version + 1}.json", arguments)
    return {"patched": True, "patch_count": len(arguments["patches"])}


def build_tool_registry(config: AppConfig) -> ToolRegistry:
    """一次性注册后续阶段共用的精简工具集合。首次使用：S2。"""

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            "search_web",
            "搜索候选网页来源；搜索摘要不属于已核验证据。",
            _object_schema(
                {
                    "query": {"type": "string"},
                    "date_range": {"type": "string", "description": "Optional day/week/month/year or empty string."},
                },
                ["query", "date_range"],
            ),
            _search_handler,
        )
    )
    registry.register(
        ToolDefinition(
            "read_page",
            "读取候选网页正文，之后才能引用其中的论断或数字。",
            _object_schema(
                {"url": {"type": "string"}, "source_id": {"type": "string"}},
                ["url", "source_id"],
            ),
            _read_handler,
        )
    )
    registry.register(
        ToolDefinition(
            "create_ppt",
            "根据完整 DeckSpec 创建最终五页 PPTX。",
            _object_schema({"deck": deck_schema(int(config.section("task")["slide_count"]))}, ["deck"]),
            _create_ppt_handler,
        )
    )
    update_schema = plan_schema()
    registry.register(
        ToolDefinition(
            "update_plan",
            "当 Observation 推翻原路径时替换当前计划。",
            _object_schema(
                {"items": update_schema["properties"]["items"], "reason": {"type": "string"}},
                ["items", "reason"],
            ),
            _update_plan_handler,
        )
    )
    registry.register(
        ToolDefinition(
            "patch_deck",
            "针对明确的评审问题替换一个或多个页面。",
            deck_patch_schema(),
            _patch_deck_handler,
        )
    )
    return registry


def _record_tool_result(context: ExecutionContext, result: ToolResult, save_payloads: bool = True) -> None:
    """记录工具结果，并只用可验证事实更新 `TaskState`。首次使用：S2。"""

    if save_payloads:
        context.recorder.record("tool_result", **result.to_dict())
    else:
        context.recorder.record(
            "tool_result",
            call_id=result.call_id,
            name=result.name,
            success=result.success,
            error=result.error,
        )
    if context.state is None:
        return
    context.state.current_step += 1
    if result.success:
        context.state.completed_actions.append(result.name)
        if result.name in {"search_web", "read_page"}:
            ids = []
            if result.name == "search_web":
                ids = [item["source_id"] for item in result.data.get("results", [])]
            elif result.data.get("source_id"):
                ids = [result.data["source_id"]]
            context.state.source_ids = list(dict.fromkeys(context.state.source_ids + ids))
    else:
        context.state.open_questions.append(f"{result.name} 失败：{result.error}")
    context.persist_state()


def execute_call(
    call: ToolCall,
    registry: ToolRegistry,
    context: ExecutionContext,
    allowed_names: list[str],
) -> ToolResult:
    """执行调用前检查阶段工具白名单和全局调用次数上限。首次使用：S2。"""

    limit = int(context.config.section("limits")["max_tool_calls"])
    if context.tool_call_count >= limit:
        return ToolResult(call.call_id, call.name, False, error=f"达到 max_tool_calls={limit}")
    context.tool_call_count += 1
    save_payloads = context.config.section("recording").get("save_tool_payloads", True)
    call_payload = {"arguments": call.arguments} if save_payloads else {}
    context.recorder.record("tool_call", call_id=call.call_id, tool_name=call.name, **call_payload)
    if call.name not in allowed_names:
        result = ToolResult(call.call_id, call.name, False, error="当前 Stage 未开放该工具")
    else:
        result = registry.execute(call, context)
    _record_tool_result(context, result, save_payloads)
    return result


def tool_output_item(result: ToolResult) -> dict[str, Any]:
    """把工具结果格式化为 Responses API 的函数输出项。首次使用：S2。"""

    return {
        "type": "function_call_output",
        "call_id": result.call_id,
        "output": json.dumps(result.to_dict(), ensure_ascii=False),
    }


def run_tool_round(
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
    prompt: str,
    instructions: str,
    allowed_names: list[str],
) -> str:
    """执行一次有边界的“模型请求—工具执行—结果回传”教学回合。首次使用：S2。"""

    schemas = registry.schemas(allowed_names)
    response = model.start_tool_turn(prompt, instructions, schemas)
    calls = model.extract_tool_calls(response)
    if not calls:
        raise ModelError("S2 预期模型发起工具调用，但模型直接返回了文本")
    results = [execute_call(call, registry, context, allowed_names) for call in calls]
    final = model.continue_tool_turn(
        response.id,
        [tool_output_item(result) for result in results],
        instructions,
        schemas,
    )
    return str(getattr(final, "output_text", "")).strip()


def run_agent_loop(
    model: OpenAIModel,
    registry: ToolRegistry,
    context: ExecutionContext,
    prompt: str,
    instructions_factory: Callable[[], str],
    allowed_names: list[str],
) -> AgentOutcome:
    """循环执行，直到模型结束、PPT 已交付、发生错误或达到步数上限。首次使用：S4。"""

    schemas = registry.schemas(allowed_names)
    max_steps = int(context.config.section("limits")["max_agent_steps"])
    max_elapsed = int(context.config.section("limits")["max_elapsed_seconds"])
    started_at = time.monotonic()
    response: Any = None
    outputs: list[dict[str, Any]] = []
    try:
        for step in range(1, max_steps + 1):
            if time.monotonic() - started_at > max_elapsed:
                outcome = AgentOutcome("limit_reached", step - 1, "", None, f"达到 max_elapsed_seconds={max_elapsed}")
                _finish_state(context, outcome.status)
                return outcome
            instructions = instructions_factory()
            if response is None:
                response = model.start_tool_turn(prompt, instructions, schemas)
            else:
                response = model.continue_tool_turn(response.id, outputs, instructions, schemas)
            calls = model.extract_tool_calls(response)
            if not calls:
                final_text = str(getattr(response, "output_text", "")).strip()
                if context.deck is not None:
                    outcome = AgentOutcome("completed", step, final_text, f"deck_v{context.deck_version}.pptx")
                else:
                    outcome = AgentOutcome("incomplete", step, final_text, None, "模型结束但未调用 create_ppt")
                _finish_state(context, outcome.status)
                return outcome
            results = [execute_call(call, registry, context, allowed_names) for call in calls]
            outputs = [tool_output_item(result) for result in results]
        outcome = AgentOutcome("limit_reached", max_steps, "", None, f"达到 max_agent_steps={max_steps}")
        _finish_state(context, outcome.status)
        return outcome
    except Exception as exc:
        outcome = AgentOutcome("error", context.state.current_step if context.state else 0, "", None, str(exc))
        _finish_state(context, outcome.status)
        return outcome


def _finish_state(context: ExecutionContext, reason: str) -> None:
    """启用显式 State 时写入并保存循环结束原因。首次使用：S5。"""

    if context.state is not None:
        context.state.termination_reason = reason
        context.persist_state()
