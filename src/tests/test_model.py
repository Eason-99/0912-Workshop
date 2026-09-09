"""离线验证 Responses API 适配器的结构化输出与工具消息链。首次覆盖：S1。"""

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from core.config import load_config
from core.context import ExecutionContext
from core.model import OpenAIModel
from core.recorder import Recorder
from core.runtime import tool_output_item
from stages.s0_api import run as run_s0


class FakeResponseStream:
    """模拟 Responses 流对象并提供最终聚合响应。首次覆盖：S1。"""

    def __init__(self, response: object) -> None:
        """保存进入上下文后要返回的最终响应。首次覆盖：S1。"""

        self.response = response

    def __enter__(self) -> "FakeResponseStream":
        """进入假流上下文并返回自身。首次覆盖：S1。"""

        return self

    def __exit__(self, *args: object) -> None:
        """退出假流上下文且不吞掉异常。首次覆盖：S1。"""

        return None

    def get_final_response(self) -> object:
        """返回预置的完整 Responses 响应。首次覆盖：S1。"""

        return self.response


class FakeResponses:
    """按顺序返回预置响应并保存请求，避免单元测试联网。首次覆盖：S1。"""

    def __init__(self, responses: list[object]) -> None:
        """保存待返回的响应和空请求列表。首次覆盖：S1。"""

        self.responses = responses
        self.requests: list[dict[str, object]] = []

    def create(self, **request: object) -> object:
        """记录一次 Responses 请求并返回下一个假响应。首次覆盖：S1。"""

        self.requests.append(request)
        return self.responses.pop(0)

    def stream(self, **request: object) -> FakeResponseStream:
        """记录一次流式请求并返回可聚合的假事件流。首次覆盖：S1。"""

        self.requests.append(request)
        return FakeResponseStream(self.responses.pop(0))


def fake_response(response_id: str, text: str, output: list[object] | None = None) -> object:
    """构造适配器可读取的最小 Responses API 响应。首次覆盖：S1。"""

    return SimpleNamespace(id=response_id, output_text=text, output=output or [], status="completed")


def fake_tool_call(call_id: str, name: str, arguments: str) -> object:
    """构造带 JSON 参数的最小 Responses 函数调用项。首次覆盖：S2。"""

    return SimpleNamespace(type="function_call", call_id=call_id, name=name, arguments=arguments)


class ModelTests(unittest.TestCase):
    """在不联网的情况下验证两个 profile 共用的 Responses 行为。首次覆盖：S1。"""

    def _model(self, responses: list[object], run_dir: Path) -> tuple[OpenAIModel, FakeResponses]:
        """绕过真实客户端初始化并注入可观察的假 Responses 客户端。首次覆盖：S1。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        recorder = Recorder(run_dir, "s2_tools")
        fake_api = FakeResponses(responses)
        model = OpenAIModel.__new__(OpenAIModel)
        model.client = SimpleNamespace(responses=fake_api)
        model.config = config
        model.recorder = recorder
        model.profile_name = "third_party"
        model.profile = {"name": "test-model", "api_mode": "responses", "supports_tool_calling": True}
        model.model_name = "test-model"
        model.model_config = config.section("model")
        model.call_count = 0
        return model, fake_api

    def test_call_log_preserves_final_request_and_raw_output(self) -> None:
        """确认统一日志保存最终 Prompt，且原始文本不被 strip。首次覆盖：S0。"""

        raw_output = "\n原始模型输出\n"
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            model, _ = self._model([fake_response("resp_1", raw_output)], run_dir)
            returned = model.generate_text("最终用户 Prompt", "最终系统指令")
            records = [
                json.loads(line)
                for line in (run_dir / "model_calls.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            saved_output = (run_dir / "model_calls/model_call_001_output.txt").read_text(
                encoding="utf-8"
            )
            saved_request = json.loads(
                (run_dir / "model_calls/model_call_001_request.json").read_text(encoding="utf-8")
            )
        self.assertEqual(returned, raw_output)
        self.assertEqual(saved_output, raw_output)
        self.assertEqual(saved_request["input"], "最终用户 Prompt")
        self.assertEqual(saved_request["instructions"], "最终系统指令")
        self.assertEqual([record["phase"] for record in records], ["request", "response"])
        self.assertEqual(records[1]["output_text"], raw_output)

    def test_s0_draft_equals_recorded_raw_output(self) -> None:
        """确认 S0 的 draft.md 与逐轮保存的原始 output_text 完全一致。首次覆盖：S0。"""

        raw_output = "\nS0 原始输出\n"
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            model, _ = self._model([fake_response("resp_1", raw_output)], run_dir)
            context = ExecutionContext(model.config, model.recorder, run_dir)
            result = run_s0(model.config, model, None, context)
            draft = Path(result["draft_path"]).read_text(encoding="utf-8")
            recorded = (run_dir / "model_calls/model_call_001_output.txt").read_text(
                encoding="utf-8"
            )
        self.assertEqual(draft, raw_output)
        self.assertEqual(draft, recorded)

    def test_structured_output_uses_responses_json_schema(self) -> None:
        """确认两个 profile 的结构化输出都使用 Responses JSON Schema。首次覆盖：S1。"""

        with tempfile.TemporaryDirectory() as temporary:
            model, fake_api = self._model(
                [fake_response("resp_1", '{"answer": "ok"}')],
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
        self.assertEqual(fake_api.requests[0]["text"]["format"]["type"], "json_schema")
        self.assertEqual(fake_api.requests[0]["max_output_tokens"], 8000)

    def test_tool_result_uses_previous_response_id(self) -> None:
        """确认工具结果通过 call ID 接回上一条 Responses 会话。首次覆盖：S2。"""

        first_call = fake_tool_call("call_1", "search_web", '{"query":"AI","date_range":"year"}')
        with tempfile.TemporaryDirectory() as temporary:
            model, fake_api = self._model(
                [fake_response("resp_1", "", [first_call]), fake_response("resp_2", "搜索完成")],
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
        self.assertEqual(fake_api.requests[1]["previous_response_id"], "resp_1")
        self.assertEqual(fake_api.requests[1]["input"][0]["type"], "function_call_output")
        self.assertEqual(fake_api.requests[1]["input"][0]["call_id"], "call_1")


if __name__ == "__main__":
    unittest.main()
