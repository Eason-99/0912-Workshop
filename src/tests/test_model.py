"""离线验证 Chat Completions 适配器的结构化输出与工具消息链。首次覆盖：S1。"""

from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from core.config import load_config
from core.model import OpenAIModel
from core.recorder import Recorder
from core.runtime import tool_output_item


class FakeCompletions:
    """按顺序返回预置响应并保存请求，避免测试调用真实 API。首次覆盖：S1。"""

    def __init__(self, responses: list[object]) -> None:
        """保存待返回的响应和空请求列表。首次覆盖：S1。"""

        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def create(self, **request: object) -> object:
        """记录一次 Chat Completions 请求并返回下一个假响应。首次覆盖：S1。"""

        self.requests.append(request)
        return self.responses.pop(0)


def fake_response(content: str | None, tool_calls: list[object] | None = None) -> object:
    """构造适配器可读取的最小 Chat Completions 响应。首次覆盖：S1。"""

    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    choice = SimpleNamespace(message=message, finish_reason="tool_calls" if tool_calls else "stop")
    return SimpleNamespace(choices=[choice])


def fake_tool_call(call_id: str, name: str, arguments: str) -> object:
    """构造带 JSON 参数的最小 SDK 风格工具调用。首次覆盖：S2。"""

    function = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(id=call_id, function=function)


class ModelTests(unittest.TestCase):
    """在不联网的情况下验证兼容模型层的请求和会话行为。首次覆盖：S1。"""

    def _model(self, responses: list[object], run_dir: Path) -> tuple[OpenAIModel, FakeCompletions]:
        """绕过真实客户端初始化并注入可观察的假客户端。首次覆盖：S1。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        recorder = Recorder(run_dir, "s2_tools")
        completions = FakeCompletions(responses)
        model = OpenAIModel.__new__(OpenAIModel)
        model.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        model.config = config
        model.recorder = recorder
        model.profile_name = "deepseek"
        model.profile = {
            "name": "deepseek-chat",
            "supports_json_object": True,
            "supports_tool_calling": True,
        }
        model.model_name = "deepseek-chat"
        model.model_config = config.section("model")
        model.call_count = 0
        model._turn_count = 0
        model._histories = {}
        return model, completions

    def test_structured_output_is_locally_validated(self) -> None:
        """确认 JSON object 响应会在返回前经过本地 Schema 校验。首次覆盖：S1。"""

        with tempfile.TemporaryDirectory() as temporary:
            model, completions = self._model(
                [fake_response('{"answer": "ok"}')],
                Path(temporary) / "run",
            )
            result = model.generate_structured(
                "返回答案",
                "只返回 JSON",
                "answer",
                {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            )
        self.assertEqual(result, {"answer": "ok"})
        self.assertEqual(completions.requests[0]["response_format"], {"type": "json_object"})

    def test_tool_result_is_appended_as_chat_tool_message(self) -> None:
        """确认工具结果通过 tool_call_id 接回同一条本地消息链。首次覆盖：S2。"""

        first_call = fake_tool_call("call_1", "search_web", '{"query":"AI","date_range":"year"}')
        with tempfile.TemporaryDirectory() as temporary:
            model, completions = self._model(
                [fake_response(None, [first_call]), fake_response("搜索完成")],
                Path(temporary) / "run",
            )
            first_turn = model.start_tool_turn("搜索", "使用工具", [])
            calls = model.extract_tool_calls(first_turn)
            output = SimpleNamespace(
                call_id=calls[0].call_id,
                to_dict=lambda: {"success": True, "data": {"count": 1}},
            )
            final_turn = model.continue_tool_turn(
                first_turn.id,
                [tool_output_item(output)],
                "根据观察总结",
                [],
            )
        self.assertEqual(final_turn.output_text, "搜索完成")
        second_messages = completions.requests[1]["messages"]
        self.assertEqual(second_messages[-1]["role"], "tool")
        self.assertEqual(second_messages[-1]["tool_call_id"], "call_1")
        self.assertEqual(second_messages[-2]["tool_calls"][0]["function"]["name"], "search_web")


if __name__ == "__main__":
    unittest.main()
