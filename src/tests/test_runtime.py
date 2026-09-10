"""测试工具注册、分派和来源核验。首次覆盖：S2。"""

from pathlib import Path
import tempfile
import unittest

from core.config import load_config
from core.context import ExecutionContext
from core.contracts import ToolCall, ToolResult
from core.recorder import Recorder
from core.runtime import build_tool_registry, run_agent_loop
from tests.test_contracts import sample_deck


class FakeRegistry:
    """返回空 Schema 并直接成功执行，避免 Agent Loop 测试联网。首次覆盖：S4。"""

    def schemas(self, names: list[str]) -> list[dict[str, object]]:
        """不向假模型暴露任何真实工具 Schema。首次覆盖：S4。"""

        return []

    def execute(self, call: ToolCall, context: ExecutionContext) -> ToolResult:
        """不执行网络动作，直接返回成功结果。首次覆盖：S4。"""

        return ToolResult(call.call_id, call.name, True, data={"ok": True})


class FakeAgentModel:
    """每轮先请求一次工具，额度耗尽后才给出文本。首次覆盖：S4。"""

    def __init__(self, tool_call_rounds: int) -> None:
        """保存请求工具的次数。首次覆盖：S4。"""

        self.remaining = tool_call_rounds
        self.turn = 0

    def _turn(self, text: str = "") -> object:
        """构造一个同时带文本与可选工具调用的最小回合。首次覆盖：S4。"""

        from types import SimpleNamespace

        self.turn += 1
        calls = []
        if self.remaining > 0:
            self.remaining -= 1
            calls = [ToolCall(f"call_{self.turn}", "search_web", {"query": "q", "date_range": ""})]
        return SimpleNamespace(id=f"resp_{self.turn}", output_text=text, tool_calls=calls)

    def start_tool_turn(self, prompt: str, instructions: str, tools: object) -> object:
        """返回首轮响应。首次覆盖：S4。"""

        return self._turn()

    def continue_tool_turn(self, response_id: str, outputs: object, instructions: str, tools: object) -> object:
        """返回后续响应；工具次数用尽后改为纯文本结束。首次覆盖：S4。"""

        return self._turn("额度已耗尽，无法交付。")

    def extract_tool_calls(self, response: object) -> list[ToolCall]:
        """返回该响应携带的工具调用。首次覆盖：S4。"""

        return list(getattr(response, "tool_calls", []))


class RuntimeTests(unittest.TestCase):
    """在不联网、不调用模型的条件下验证工具分派。首次覆盖：S2。"""

    def test_tool_schema_uses_responses_shape(self) -> None:
        """确认工具定义使用 Responses API 要求的扁平函数结构。首次覆盖：S2。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        schema = build_tool_registry(config).schemas(["search_web"])[0]
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["name"], "search_web")
        self.assertIn("parameters", schema)
        self.assertTrue(schema["strict"])

    def test_unknown_tool_returns_observation(self) -> None:
        """确认未知工具会转换为失败的 ToolResult。首次覆盖：S2。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        registry = build_tool_registry(config)
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            context = ExecutionContext(config, Recorder(run_dir, "s2_tools"), run_dir)
            result = registry.execute(ToolCall("c1", "missing", {}), context)
            self.assertFalse(result.success)

    def test_create_ppt_rejects_unread_sources(self) -> None:
        """确认 PPT 生成前会拒绝只搜索但未读页的来源。首次覆盖：S2。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        registry = build_tool_registry(config)
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            context = ExecutionContext(config, Recorder(run_dir, "s4_agent"), run_dir)
            context.sources["src_candidate"] = {"source_id": "src_candidate", "status": "candidate_only"}
            deck = sample_deck()
            deck["slides"][0]["source_ids"] = ["src_candidate"]
            result = registry.execute(ToolCall("c2", "create_ppt", {"deck": deck}), context)
            self.assertFalse(result.success)
            self.assertIn("尚未 read_page", result.error or "")

    def test_exhausted_tool_budget_is_reported_as_limit_reached(self) -> None:
        """确认额度耗尽导致未交付时报 limit_reached，而不是笼统的 incomplete。首次覆盖：S4。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        config.data["limits"]["max_tool_calls"] = 2
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            context = ExecutionContext(config, Recorder(run_dir, "s4_agent"), run_dir)
            # 先请求 4 次工具（超过额度 2），再进行一次不带工具调用的收尾。
            outcome = run_agent_loop(
                FakeAgentModel(tool_call_rounds=4),
                FakeRegistry(),
                context,
                "任务",
                lambda: "指令",
                ["search_web"],
            )
        self.assertEqual(context.tool_call_count, 2)
        self.assertIsNone(outcome.deck_path)
        self.assertEqual(outcome.status, "limit_reached")
        self.assertIn("max_tool_calls=2", outcome.error or "")


if __name__ == "__main__":
    unittest.main()
