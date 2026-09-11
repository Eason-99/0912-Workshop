"""统一封装两个 profile 的 OpenAI-compatible Responses API 调用。首次使用：S0。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from core.config import AppConfig
from core.contracts import ContractError, ToolCall
from core.recorder import Recorder


class ModelError(RuntimeError):
    """表示模型请求失败或返回空白、不完整结果。首次使用：S0。"""


# 工具结果回传时，上一轮输出项的三种回放策略，用于适配不同服务商的会话实现。
REPLAY_MODES = ("none", "function_call", "full")


def _resolve_replay_mode(profile: dict[str, Any]) -> str:
    """解析当前 profile 的回放策略，并兼容旧的 `replay_previous_output` 开关。首次使用：S2。"""

    mode = profile.get("tool_call_replay")
    if mode is None:
        return "full" if profile.get("replay_previous_output") else "none"
    return str(mode)


def _replay_items(mode: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按策略挑出要回放的输出项：完整回放，或只回放最小化的 function_call。首次使用：S2。"""

    if mode == "full":
        return list(items)
    if mode == "function_call":
        # 只保留必要字段：部分服务商会拒绝输出项里的 status/id 等附加键。
        return [
            {
                "type": "function_call",
                "call_id": str(item["call_id"]),
                "name": str(item["name"]),
                "arguments": str(item["arguments"]),
            }
            for item in items
            if item.get("type") == "function_call"
        ]
    return []


@dataclass(frozen=True)
class ModelTurn:
    """保存一次 Responses API 回合的 ID、文本与工具调用。首次使用：S0。"""

    id: str
    output_text: str
    tool_calls: list[ToolCall]


def _exception_chain(exc: Exception) -> str:
    """提取异常类型及底层原因，避免只显示笼统的 Connection error。首次使用：S0。"""

    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(parts) < 6:
        message = str(current).strip() or "无详细信息"
        parts.append(f"{type(current).__name__}: {message}")
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)


class OpenAIModel:
    """用相同 Responses 接口适配 DeepSeek 与第三方 URL/Key。首次使用：S0。"""

    def __init__(self, config: AppConfig, recorder: Recorder) -> None:
        """从 active profile 和 `.env` 创建 Responses API 客户端。首次使用：S0。"""

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ModelError("缺少 openai；请执行 `pip install -r src/requirements.txt`") from exc

        model_config = config.section("model")
        profile_name, profile = config.active_model_profile()
        api_key, base_url = config.model_connection()
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(model_config.get("timeout_seconds", 120)),
            max_retries=int(model_config.get("max_retries", 3)),
        )
        self.config = config
        self.recorder = recorder
        self.profile_name = profile_name
        self.profile = profile
        self.model_name = str(profile["name"])
        self.model_config = model_config
        self.call_count = 0
        # 可选：让推理模型降低思考深度，缩短每个响应的时间；仅当前 profile 显式配置时才发送。
        self.reasoning_effort = profile.get("reasoning_effort")
        # 部分兼容服务不依据 previous_response_id 复原工具调用链，必须在下一轮请求中
        # 回放上一轮的调用项，否则报“找不到 call_id 对应的工具调用”。
        self.tool_call_replay = _resolve_replay_mode(profile)
        # 按 response id 暂存上一轮原始输出项，供下一轮工具结果请求回放。
        self._pending_output_items: dict[str, list[dict[str, Any]]] = {}

    def generate_text(self, prompt: str, instructions: str) -> str:
        """执行一次普通 Responses 文本生成。首次使用：S0。"""

        turn = self._create(input=prompt, instructions=instructions)
        if not turn.output_text.strip():
            raise ModelError("模型未返回文本")
        return turn.output_text

    def generate_structured(
        self,
        prompt: str,
        instructions: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """请求严格 JSON Schema 输出并解析为字典。首次使用：S1。"""

        turn = self._create(
            input=prompt,
            instructions=instructions,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        if not turn.output_text:
            raise ModelError("模型未返回结构化文本，可能发生拒绝或输出中断")
        try:
            value = json.loads(turn.output_text)
        except json.JSONDecodeError as exc:
            raise ContractError("模型结构化输出不是合法 JSON") from exc
        if not isinstance(value, dict):
            raise ContractError("模型结构化输出根节点必须是 object")
        return value

    def start_tool_turn(
        self,
        prompt: str,
        instructions: str,
        tools: list[dict[str, Any]],
    ) -> ModelTurn:
        """开始一个允许模型发起 Responses 函数调用的新回合。首次使用：S2。"""

        if not self.profile["supports_tool_calling"]:
            raise ModelError(f"模型 profile `{self.profile_name}` 不支持工具调用")
        return self._create(input=prompt, instructions=instructions, tools=tools)

    def continue_tool_turn(
        self,
        previous_turn_id: str,
        function_outputs: list[dict[str, Any]],
        instructions: str,
        tools: list[dict[str, Any]],
        tool_choice: str | None = None,
    ) -> ModelTurn:
        """使用 response ID 与 call ID 把工具观察送回模型。首次使用：S2。

        `tool_choice` 为 `"none"` 时，本轮禁止再次发起工具调用，用于让固定教学回合
        在回传观察后必须给出文本总结。
        """

        # 需要回放的 provider 先补上上一轮的调用项，再放工具输出。
        stored = self._pending_output_items.pop(previous_turn_id, [])
        replayed = _replay_items(self.tool_call_replay, stored)
        choice = {} if tool_choice is None else {"tool_choice": tool_choice}
        return self._create(
            previous_response_id=previous_turn_id,
            input=replayed + function_outputs,
            instructions=instructions,
            tools=tools,
            **choice,
        )

    def extract_tool_calls(self, response: ModelTurn) -> list[ToolCall]:
        """返回已经从 Responses 输出解析出的共享工具调用。首次使用：S2。"""

        return list(response.tool_calls)

    def _create(self, **kwargs: Any) -> ModelTurn:
        """应用模型参数、上限、重试和日志后执行一次 Responses 请求。首次使用：S0。"""

        limit = int(self.config.section("limits")["max_model_calls"])
        if self.call_count >= limit:
            raise ModelError(f"达到 max_model_calls={limit}")
        self.call_count += 1
        call_id = f"model_call_{self.call_count:03d}"
        request: dict[str, Any] = {
            "model": self.model_name,
            "max_output_tokens": int(self.model_config.get("max_output_tokens", 8000)),
            **kwargs,
        }
        temperature = self.model_config.get("temperature")
        if temperature is not None:
            request["temperature"] = float(temperature)
        if self.reasoning_effort:
            request["reasoning"] = {"effort": str(self.reasoning_effort)}
        save_messages = self.config.section("recording").get("save_messages", True)
        self.recorder.record_model_request(
            call_id=call_id,
            call_number=self.call_count,
            profile=self.profile_name,
            api_mode="responses",
            request=request,
        )
        try:
            if self.model_config.get("use_streaming", True):
                response = self._stream_response(**request)
            else:
                response = self.client.responses.create(**request)
        except Exception as exc:
            detail = _exception_chain(exc)
            self.recorder.record_model_error(
                call_id=call_id,
                call_number=self.call_count,
                profile=self.profile_name,
                api_mode="responses",
                error=detail,
            )
            raise ModelError(f"模型 profile `{self.profile_name}` Responses 调用失败：{detail}") from exc
        dumped = response.model_dump(mode="json") if hasattr(response, "model_dump") else str(response)
        raw_output_text = str(getattr(response, "output_text", "") or "")
        status = getattr(response, "status", None)
        response_id = str(response.id)
        self.recorder.record_model_response(
            call_id=call_id,
            call_number=self.call_count,
            response_id=response_id,
            status=status,
            output_text=raw_output_text,
            provider_response=dumped,
            save_provider_response=bool(save_messages),
        )
        if status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            raise ModelError(
                f"模型输出被截断，未生成完整结果（incomplete_details={details}）。"
                "可提高 model.max_output_tokens，或减少单次请求需要生成的内容。"
            )
        output_items = getattr(response, "output", [])
        # 只有包含函数调用的响应才需要留存回放，避免无用地累积上下文。
        if self.tool_call_replay != "none" and any(
            getattr(item, "type", None) == "function_call" for item in output_items
        ):
            self._pending_output_items[response_id] = self._dump_output_items(output_items)
        return ModelTurn(
            id=response_id,
            output_text=raw_output_text,
            tool_calls=self._parse_tool_calls(output_items),
        )

    def _stream_response(self, **request: Any) -> Any:
        """消费 Responses 事件流，并返回终止事件携带的完整响应。首次使用：S0。

        OpenAI SDK 的 `get_final_response()` 只承认 `response.completed`；当服务端以
        `response.incomplete`（例如达到 `max_output_tokens`）或 `response.failed` 结束时，
        它会抛出 “Didn't receive a `response.completed` event.” 并丢掉真实原因。
        这里显式读取终止事件，把真实响应交回上层，从而报出截断或失败的具体原因。
        """

        terminal: Any = None
        with self.client.responses.stream(**request) as stream:
            for event in stream:
                if getattr(event, "type", None) in (
                    "response.completed",
                    "response.incomplete",
                    "response.failed",
                ):
                    terminal = event
                    break
        if terminal is None:
            raise ModelError("流式响应在返回终止事件前结束，未收到 completed/incomplete/failed")
        response = getattr(terminal, "response", None)
        if response is None:
            raise ModelError(f"终止事件 `{getattr(terminal, 'type', 'unknown')}` 未携带完整响应")
        return response

    def _dump_output_items(self, output: list[Any]) -> list[dict[str, Any]]:
        """把上一轮输出项转为可原样回放的 JSON 字典。首次使用：S2。"""

        items: list[dict[str, Any]] = []
        for item in output:
            if hasattr(item, "model_dump"):
                items.append(item.model_dump(mode="json"))
            elif isinstance(item, dict):
                items.append(item)
        return items

    def _parse_tool_calls(self, output: list[Any]) -> list[ToolCall]:
        """把 Responses 函数调用项转换为共享 `ToolCall`。首次使用：S2。"""

        calls: list[ToolCall] = []
        for item in output:
            if getattr(item, "type", None) != "function_call":
                continue
            name = str(item.name)
            try:
                arguments = json.loads(item.arguments)
            except json.JSONDecodeError as exc:
                raise ContractError(f"工具 `{name}` 参数不是合法 JSON") from exc
            if not isinstance(arguments, dict):
                raise ContractError(f"工具 `{name}` 参数根节点必须是 object")
            calls.append(ToolCall(call_id=str(item.call_id), name=name, arguments=arguments))
        return calls
