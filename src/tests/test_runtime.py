"""测试工具注册、分派和来源核验。首次覆盖：S2。"""

from pathlib import Path
import tempfile
import unittest

from core.config import load_config
from core.context import ExecutionContext
from core.contracts import ToolCall
from core.recorder import Recorder
from core.runtime import build_tool_registry
from tests.test_contracts import sample_deck


class RuntimeTests(unittest.TestCase):
    """在不联网、不调用模型的条件下验证工具分派。首次覆盖：S2。"""

    def test_tool_schema_uses_chat_completions_shape(self) -> None:
        """确认工具定义使用 Chat Completions 要求的 function 嵌套。首次覆盖：S2。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        schema = build_tool_registry(config).schemas(["search_web"])[0]
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "search_web")
        self.assertIn("parameters", schema["function"])

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


if __name__ == "__main__":
    unittest.main()
