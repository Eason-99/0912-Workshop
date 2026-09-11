"""离线验证 Responses API 适配器的结构化输出与工具消息链。首次覆盖：S1。"""

from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest

from core.config import load_config
from core.context import ExecutionContext
from core.model import ModelError, OpenAIModel
from core.recorder import Recorder
from core.runtime import tool_output_item
from stages.s0_api import run as run_s0


class FakeResponseStream:
    """模拟 Responses 事件流，按响应状态产出终止事件。首次覆盖：S1。"""

    def __init__(self, response: object) -> None:
        """保存进入上下文后要作为终止事件负载返回的响应。首次覆盖：S1。"""

        self.response = response

    def __enter__(self) -> "FakeResponseStream":
        """进入假流上下文并返回自身。首次覆盖：S1。"""

        return self

    def __exit__(self, *args: object) -> None:
        """退出假流上下文且不吞掉异常。首次覆盖：S1。"""

        return None

    def __iter__(self):
        """产出 completed 或 incomplete 终止事件；后者用于验证截断处理。首次覆盖：S1。"""

        event_type = (
            "response.incomplete"
            if getattr(self.response, "status", None) == "incomplete"
            else "response.completed"
        )
        yield SimpleNamespace(type=event_type, response=self.response)


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


def fake_incomplete_response(response_id: str, text: str, reason: str = "max_output_tokens") -> object:
    """构造被 max_output_tokens 截断的响应。首次覆盖：S3。"""

    return SimpleNamespace(
        id=response_id,
        output_text=text,
        output=[],
        status="incomplete",
        incomplete_details=SimpleNamespace(reason=reason),
    )


def fake_tool_call(call_id: str, name: str, arguments: str) -> object:
    """构造带 JSON 参数的最小 Responses 函数调用项。首次覆盖：S2。"""

    return SimpleNamespace(type="function_call", call_id=call_id, name=name, arguments=arguments)


def fake_output_item(payload: dict[str, object]) -> object:
    """构造可回放的原始输出项，模拟 SDK 的 model_dump。首次覆盖：S2。"""

    item = SimpleNamespace(**payload)
    item.model_dump = lambda mode="python": dict(payload)
    return item


class ModelTests(unittest.TestCase):
    """在不联网的情况下验证两个 profile 共用的 Responses 行为。首次覆盖：S1。"""

    def _model(
        self,
        responses: list[object],
        run_dir: Path,
        replay_previous_output: bool = False,
        tool_call_replay: str | None = None,
        reasoning_effort: str | None = None,
    ) -> tuple[OpenAIModel, FakeResponses]:
        """绕过真实客户端初始化并注入可观察的假 Responses 客户端。首次覆盖：S1。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        recorder = Recorder(run_dir, "s2_tools")
        fake_api = FakeResponses(responses)
        model = OpenAIModel.__new__(OpenAIModel)
        model.client = SimpleNamespace(responses=fake_api)
        model.config = config
        model.recorder = recorder
        model.profile_name = "third_party"
        profile: dict[str, object] = {
            "name": "test-model",
            "api_mode": "responses",
            "supports_tool_calling": True,
            "replay_previous_output": replay_previous_output,
        }
        if tool_call_replay is not None:
            profile["tool_call_replay"] = tool_call_replay
        if reasoning_effort is not None:
            profile["reasoning_effort"] = reasoning_effort
        model.profile = profile
        model.model_name = "test-model"
        model.model_config = config.section("model")
        model.call_count = 0
        model.tool_call_replay = tool_call_replay or (
            "full" if replay_previous_output else "none"
        )
        model._pending_output_items = {}
        model.reasoning_effort = reasoning_effort
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
        # 与配置保持一致，避免把可在 config.yaml 调整的上限写死在测试里。
        self.assertEqual(
            fake_api.requests[0]["max_output_tokens"],
            model.config.section("model")["max_output_tokens"],
        )

    def test_incomplete_stream_reports_real_reason(self) -> None:
        """确认被截断的流式响应报出真实原因，而不是 SDK 的笼统 RuntimeError。首次覆盖：S3。"""

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            model, _ = self._model([fake_incomplete_response("resp_1", "被截断的部分输出")], run_dir)
            with self.assertRaises(ModelError) as context:
                model.generate_text("提示", "指令")
            partial = (run_dir / "model_calls/model_call_001_output.txt").read_text(encoding="utf-8")
        self.assertIn("max_output_tokens", str(context.exception))
        self.assertIn("max_output_tokens", json.dumps(context.exception.args, ensure_ascii=False))
        # 截断时的部分输出仍要落盘，便于复盘。
        self.assertEqual(partial, "被截断的部分输出")

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

    def test_replay_profile_resends_previous_output_items(self) -> None:
        """确认需要回放的 profile 会先补上 reasoning 与 function_call。首次覆盖：S2。"""

        reasoning = fake_output_item(
            {"type": "reasoning", "id": "rs_1", "content": [{"type": "reasoning_text", "text": "思考"}]}
        )
        call_item = fake_output_item(
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "search_web",
                "arguments": '{"query":"AI","date_range":"year"}',
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            model, fake_api = self._model(
                [fake_response("resp_1", "", [reasoning, call_item]), fake_response("resp_2", "完成")],
                Path(temporary) / "run",
                replay_previous_output=True,
            )
            first_turn = model.start_tool_turn("搜索", "使用工具", [])
            output = SimpleNamespace(
                call_id="call_1",
                to_dict=lambda: {"success": True, "data": {"count": 1}},
            )
            model.continue_tool_turn(first_turn.id, [tool_output_item(output)], "总结", [])
            sent = fake_api.requests[1]["input"]
            self.assertEqual([item["type"] for item in sent], ["reasoning", "function_call", "function_call_output"])
            self.assertEqual(sent[1]["call_id"], "call_1")
            self.assertEqual(sent[2]["call_id"], "call_1")
        # 回放数据在消费后即释放，避免同一响应被重复回放。
        self.assertEqual(model._pending_output_items, {})

    def test_function_call_replay_mode_sends_minimal_item(self) -> None:
        """确认 function_call 模式只回放最小字段，避免服务商拒绝附加键。首次覆盖：S2。"""

        reasoning = fake_output_item(
            {"type": "reasoning", "id": "rs_1", "status": "completed", "content": []}
        )
        call_item = fake_output_item(
            {
                "type": "function_call",
                "id": "fc_1",
                "status": "completed",
                "call_id": "call_1",
                "name": "search_web",
                "arguments": '{"query":"AI","date_range":""}',
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            model, fake_api = self._model(
                [fake_response("resp_1", "", [reasoning, call_item]), fake_response("resp_2", "完成")],
                Path(temporary) / "run",
                tool_call_replay="function_call",
            )
            first_turn = model.start_tool_turn("搜索", "使用工具", [])
            output = SimpleNamespace(
                call_id="call_1", to_dict=lambda: {"success": True, "data": {}}
            )
            model.continue_tool_turn(first_turn.id, [tool_output_item(output)], "总结", [])
            sent = fake_api.requests[1]["input"]
        self.assertEqual([item["type"] for item in sent], ["function_call", "function_call_output"])
        # 不能带 status / id 这类服务商不认识的键。
        self.assertEqual(set(sent[0]), {"type", "call_id", "name", "arguments"})

    def test_none_replay_mode_sends_only_tool_output(self) -> None:
        """确认 none 模式不回放任何上一轮内容，适用于服务端自己维护会话的端点。首次覆盖：S2。"""

        call_item = fake_output_item(
            {"type": "function_call", "call_id": "call_1", "name": "search_web", "arguments": "{}"}
        )
        with tempfile.TemporaryDirectory() as temporary:
            model, fake_api = self._model(
                [fake_response("resp_1", "", [call_item]), fake_response("resp_2", "完成")],
                Path(temporary) / "run",
                tool_call_replay="none",
            )
            first_turn = model.start_tool_turn("搜索", "使用工具", [])
            output = SimpleNamespace(
                call_id="call_1", to_dict=lambda: {"success": True, "data": {}}
            )
            model.continue_tool_turn(first_turn.id, [tool_output_item(output)], "总结", [])
            sent = fake_api.requests[1]["input"]
        self.assertEqual([item["type"] for item in sent], ["function_call_output"])

    def test_reasoning_effort_is_passed_when_configured(self) -> None:
        """确认 profile 配置了 reasoning_effort 时，请求会带上 reasoning 参数。首次覆盖：S4。"""

        with tempfile.TemporaryDirectory() as temporary:
            model, fake_api = self._model(
                [fake_response("resp_1", "ok")],
                Path(temporary) / "run",
                reasoning_effort="low",
            )
            model.generate_text("提示", "指令")
            request = fake_api.requests[0]
        self.assertEqual(request["reasoning"], {"effort": "low"})


if __name__ == "__main__":
    unittest.main()
