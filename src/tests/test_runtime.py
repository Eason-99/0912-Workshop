"""测试工具注册、分派和来源核验。首次覆盖：S2。"""

from pathlib import Path
import tempfile
import unittest

from core.config import load_config
from core.context import ExecutionContext
from core.contracts import TaskState, ToolCall, ToolResult
from core.recorder import Recorder
from core.runtime import build_tool_registry, execute_call, run_agent_loop
from tests.test_contracts import sample_deck


class FakeRegistry:
    """返回空 Schema 并直接成功执行，避免 Agent Loop 测试联网。首次覆盖：S4。"""

    def schemas(self, names: list[str]) -> list[dict[str, object]]:
        """不向假模型暴露任何真实工具 Schema。首次覆盖：S4。"""

        return []

    def execute(self, call: ToolCall, context: ExecutionContext) -> ToolResult:
        """不执行网络动作，直接返回成功结果。首次覆盖：S4。"""

        return ToolResult(call.call_id, call.name, True, data={"ok": True})


class CountingRegistry(FakeRegistry):
    """记录真实执行次数，用于验证重复调用不会再次执行。首次覆盖：S4。"""

    def __init__(self) -> None:
        """初始化执行计数器。首次覆盖：S4。"""

        self.executed = 0

    def execute(self, call: ToolCall, context: ExecutionContext) -> ToolResult:
        """累计执行次数并返回带序号的结果。首次覆盖：S4。"""

        self.executed += 1
        return ToolResult(call.call_id, call.name, True, data={"ok": True, "run": self.executed})


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
            # 每轮查询词不同，避免被重复调用缓存拦下，从而真正消耗额度。
            calls = [
                ToolCall(
                    f"call_{self.turn}",
                    "search_web",
                    {"query": f"query_{self.turn}", "date_range": ""},
                )
            ]
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

    def test_duplicate_call_is_served_from_cache_without_spending_budget(self) -> None:
        """确认重复调用复用缓存、不再执行，也不消耗工具额度。首次覆盖：S4。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        registry = CountingRegistry()
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            context = ExecutionContext(config, Recorder(run_dir, "s4_agent"), run_dir)
            context.state = TaskState(goal="目标", metric_scope={})
            arguments = {"url": "https://example.com/a", "source_id": "src_1"}
            first = execute_call(ToolCall("c1", "read_page", arguments), registry, context, ["read_page"])
            second = execute_call(ToolCall("c2", "read_page", arguments), registry, context, ["read_page"])
        self.assertEqual(registry.executed, 1)
        self.assertEqual(first.data["run"], 1)
        self.assertTrue(second.data.get("duplicate"))
        self.assertEqual(second.data["run"], 1)
        self.assertEqual(context.tool_call_count, 1)
        self.assertEqual(context.duplicate_call_count, 1)

    def test_state_separates_verified_and_candidate_sources(self) -> None:
        """确认 State 区分已核验来源与搜索候选，避免模型引用未读来源。首次使用：S5。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        registry = build_tool_registry(config)
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            context = ExecutionContext(config, Recorder(run_dir, "s5_state"), run_dir)
            state = TaskState(goal="目标", metric_scope={})
            context.state = state
            context.sources["src_read"] = {"source_id": "src_read", "status": "page_read"}
            _search_handler, _read_handler = None, None
            # 表格化的最小验证：直接复用 runtime 的记录函数，避免联网。
            from core.runtime import _record_tool_result

            _record_tool_result(
                context,
                ToolResult(
                    "c1",
                    "search_web",
                    True,
                    data={"results": [{"source_id": "src_candidate"}, {"source_id": "src_read"}]},
                ),
            )
            _record_tool_result(
                context,
                ToolResult("c2", "read_page", True, data={"source_id": "src_read"}),
            )
        self.assertEqual(state.candidate_source_ids, ["src_candidate"])
        self.assertEqual(state.verified_source_ids, ["src_read"])

    def test_research_budget_blocks_search_but_keeps_delivery_open(self) -> None:
        """确认调研额度用尽后只拦截检索类工具，create_ppt 仍可调用。首次覆盖：S4。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        config.data["limits"]["max_research_tool_calls"] = 1
        registry = CountingRegistry()
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary) / "run"
            context = ExecutionContext(config, Recorder(run_dir, "s4_agent"), run_dir)
            allowed = ["search_web", "read_page", "create_ppt"]
            first = execute_call(
                ToolCall("c1", "search_web", {"query": "q1", "date_range": ""}),
                registry,
                context,
                allowed,
            )
            blocked = execute_call(
                ToolCall("c2", "search_web", {"query": "q2", "date_range": ""}),
                registry,
                context,
                allowed,
            )
            delivery = execute_call(ToolCall("c3", "create_ppt", {}), registry, context, allowed)
        self.assertTrue(first.success)
        self.assertFalse(blocked.success)
        self.assertIn("max_research_tool_calls", blocked.error or "")
        # create_ppt 不在调研工具集合内，仍会真正执行（此处由假注册表返回成功）。
        self.assertTrue(delivery.success)
        self.assertEqual(registry.executed, 2)


if __name__ == "__main__":
    unittest.main()
