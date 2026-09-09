"""封装 DeepSeek/第三方 OpenAI-compatible Chat Completions 调用。首次使用：S0。"""

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
class ChatTurn:
    """保存一次兼容 Chat Completions 的结果和本地会话 ID。首次使用：S0。"""

    id: str
    output_text: str
    tool_calls: list[ToolCall]


def _validate_json_value(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """按 Demo 使用的 JSON Schema 子集递归校验模型输出。首次使用：S1。"""

    expected = schema.get("type")
    type_matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }
    if expected in type_matches and not type_matches[expected]:
        raise ContractError(f"模型结构化输出 `{path}` 必须是 {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"模型结构化输出 `{path}` 必须是 {schema['enum']} 之一")
    if expected == "object":
        properties = schema.get("properties", {})
        missing = [field for field in schema.get("required", []) if field not in value]
        if missing:
            raise ContractError(f"模型结构化输出 `{path}` 缺少字段：{missing}")
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ContractError(f"模型结构化输出 `{path}` 包含未知字段：{extras}")
        for field, item in value.items():
            if field in properties:
                _validate_json_value(item, properties[field], f"{path}.{field}")
    elif expected == "array":
        if len(value) < int(schema.get("minItems", 0)):
            raise ContractError(f"模型结构化输出 `{path}` 数量不足")
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            raise ContractError(f"模型结构化输出 `{path}` 数量过多")
        for index, item in enumerate(value):
            _validate_json_value(item, schema.get("items", {}), f"{path}[{index}]")


class OpenAIModel:
    """用一个接口适配 DeepSeek 与第三方 OpenAI-compatible 服务。首次使用：S0。"""

    def __init__(self, config: AppConfig, recorder: Recorder) -> None:
        """按 active profile 从 `.env` 读取连接信息并创建客户端。首次使用：S0。"""

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
        )
        self.config = config
        self.recorder = recorder
        self.profile_name = profile_name
        self.profile = profile
        self.model_name = str(profile["name"])
        self.model_config = model_config
        self.call_count = 0
        self._turn_count = 0
        self._histories: dict[str, list[dict[str, Any]]] = {}

    def generate_text(self, prompt: str, instructions: str) -> str:
        """执行一次普通自由文本生成。首次使用：S0。"""

        turn = self._complete(self._new_messages(prompt, instructions))
        if not turn.output_text:
            raise ModelError("模型未返回文本")
        return turn.output_text

    def generate_structured(
        self,
        prompt: str,
        instructions: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """请求 JSON object，解析后再执行本地 Schema 校验。首次使用：S1。"""

        schema_text = json.dumps(schema, ensure_ascii=False, indent=2)
        structured_prompt = (
            f"{prompt}\n\n只返回一个名为 `{schema_name}` 的 JSON object，不要输出 Markdown 代码块或解释。"
            f"\n必须满足以下 JSON Schema：\n{schema_text}"
        )
        response_format = (
            {"type": "json_object"} if self.profile["supports_json_object"] else None
        )
        turn = self._complete(
            self._new_messages(structured_prompt, instructions),
            response_format=response_format,
        )
        if not turn.output_text:
            raise ModelError("模型未返回结构化文本")
        try:
            value = json.loads(turn.output_text)
        except json.JSONDecodeError as exc:
            raise ContractError("模型结构化输出不是合法 JSON") from exc
        if not isinstance(value, dict):
            raise ContractError("模型结构化输出根节点必须是 object")
        _validate_json_value(value, schema)
        return value

    def start_tool_turn(
        self,
        prompt: str,
        instructions: str,
        tools: list[dict[str, Any]],
    ) -> ChatTurn:
        """开始一个允许模型发起 Chat Tool Calling 的新回合。首次使用：S2。"""

        if not self.profile["supports_tool_calling"]:
            raise ModelError(f"模型 profile `{self.profile_name}` 不支持工具调用")
        return self._complete(self._new_messages(prompt, instructions), tools=tools)

    def continue_tool_turn(
        self,
        previous_turn_id: str,
        function_outputs: list[dict[str, Any]],
        instructions: str,
        tools: list[dict[str, Any]],
    ) -> ChatTurn:
        """把工具消息追加到指定本地会话，再请求下一次模型决策。首次使用：S2。"""

        previous = self._histories.get(previous_turn_id)
        if previous is None:
            raise ModelError(f"找不到上一回合：{previous_turn_id}")
        messages = [dict(message) for message in previous]
        if messages and messages[0].get("role") == "system":
            messages[0] = {"role": "system", "content": instructions}
        messages.extend(function_outputs)
        return self._complete(messages, tools=tools)

    def extract_tool_calls(self, response: ChatTurn) -> list[ToolCall]:
        """返回已从 Chat Completions 消息解析出的共享工具调用。首次使用：S2。"""

        return list(response.tool_calls)

    def _new_messages(self, prompt: str, instructions: str) -> list[dict[str, str]]:
        """将系统指令与用户任务转换为新的 Chat 消息列表。首次使用：S0。"""

        return [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ]

    def _complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        response_format: dict[str, str] | None = None,
    ) -> ChatTurn:
        """应用公共参数、调用上限和日志，并保存本地消息历史。首次使用：S0。"""

        limit = int(self.config.section("limits")["max_model_calls"])
        if self.call_count >= limit:
            raise ModelError(f"达到 max_model_calls={limit}")
        self.call_count += 1
        request: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": int(self.model_config.get("max_output_tokens", 8000)),
        }
        temperature = self.model_config.get("temperature")
        if temperature is not None:
            request["temperature"] = float(temperature)
        if tools:
            request["tools"] = tools
        if response_format is not None:
            request["response_format"] = response_format
        save_messages = self.config.section("recording").get("save_messages", True)
        if save_messages:
            self.recorder.record("model_request", call_number=self.call_count, request=request)
        else:
            self.recorder.record(
                "model_request",
                call_number=self.call_count,
                profile=self.profile_name,
                model=self.model_name,
            )
        try:
            response = self.client.chat.completions.create(**request)
        except Exception as exc:
            raise ModelError(f"模型 profile `{self.profile_name}` 调用失败：{exc}") from exc
        if not getattr(response, "choices", None):
            raise ModelError("模型没有返回 choices")
        dumped = response.model_dump(mode="json") if hasattr(response, "model_dump") else str(response)
        if save_messages:
            self.recorder.record("model_response", call_number=self.call_count, response=dumped)
        else:
            self.recorder.record(
                "model_response",
                call_number=self.call_count,
                finish_reason=getattr(response.choices[0], "finish_reason", None),
            )
        choice = response.choices[0]
        if getattr(choice, "finish_reason", None) == "length":
            raise ModelError("模型输出因 Token 上限被截断")
        message = choice.message
        content = str(message.content or "").strip()
        parsed_calls, wire_calls = self._parse_tool_calls(getattr(message, "tool_calls", None) or [])
        assistant_message: dict[str, Any] = {"role": "assistant", "content": message.content}
        if wire_calls:
            assistant_message["tool_calls"] = wire_calls
        self._turn_count += 1
        turn_id = f"chat_turn_{self._turn_count:04d}"
        self._histories[turn_id] = [*messages, assistant_message]
        return ChatTurn(turn_id, content, parsed_calls)

    def _parse_tool_calls(self, raw_calls: list[Any]) -> tuple[list[ToolCall], list[dict[str, Any]]]:
        """解析 SDK 工具调用，并构造下一回合所需的 assistant 消息。首次使用：S2。"""

        parsed: list[ToolCall] = []
        wire: list[dict[str, Any]] = []
        for call in raw_calls:
            call_id = str(call.id)
            name = str(call.function.name)
            raw_arguments = str(call.function.arguments)
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise ContractError(f"工具 `{name}` 参数不是合法 JSON") from exc
            if not isinstance(arguments, dict):
                raise ContractError(f"工具 `{name}` 参数根节点必须是 object")
            parsed.append(ToolCall(call_id=call_id, name=name, arguments=arguments))
            wire.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": raw_arguments},
                }
            )
        return parsed, wire
