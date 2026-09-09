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
    ) -> ModelTurn:
        """使用 response ID 与 call ID 把工具观察送回模型。首次使用：S2。"""

        return self._create(
            previous_response_id=previous_turn_id,
            input=function_outputs,
            instructions=instructions,
            tools=tools,
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
                with self.client.responses.stream(**request) as stream:
                    response = stream.get_final_response()
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
            raise ModelError(f"模型输出不完整：{details}")
        return ModelTurn(
            id=response_id,
            output_text=raw_output_text,
            tool_calls=self._parse_tool_calls(getattr(response, "output", [])),
        )

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
