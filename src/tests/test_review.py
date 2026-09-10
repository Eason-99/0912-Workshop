"""测试 S7 使用的确定性评审规则。首次覆盖：S7。"""

from pathlib import Path
import unittest

from core.config import load_config
from tests.test_contracts import sample_deck
from tools.review import check_deck


class ReviewTests(unittest.TestCase):
    """校验数字来源和份额标签反馈。首次覆盖：S7。"""

    def test_numeric_claim_without_source_is_flagged(self) -> None:
        """确认没有来源的数字论断会被标记。首次覆盖：S7。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        deck = sample_deck()
        deck["slides"][1]["bullets"] = ["某产品 MAU 为 1000 万"]
        issue_types = {item["type"] for item in check_deck(deck, set(), config)}
        self.assertIn("numeric_claim_without_source", issue_types)

    def test_generic_share_label_is_flagged(self) -> None:
        """确认份额必须使用准确的样本内标签。首次覆盖：S7。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        deck = sample_deck()
        deck["slides"][1]["bullets"] = ["市场份额领先"]
        issue_types = {item["type"] for item in check_deck(deck, set(), config)}
        self.assertIn("share_label", issue_types)

    def test_share_page_without_chart_or_gap_is_flagged(self) -> None:
        """确认份额页既没有图表也没有缺口声明时会被标记。首次覆盖：S7。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        deck = sample_deck()
        deck["slides"][1]["bullets"] = ["样本内 MAU 份额：豆包 49.9%、千问 21.9%"]
        issue_types = {
            item["type"] for item in check_deck(deck, set(), config) if item["slide_id"] == "s2"
        }
        self.assertIn("chart_missing", issue_types)

    def test_share_page_with_chart_passes_chart_rule(self) -> None:
        """确认给出自洽图表后不再报缺图。首次覆盖：S7。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        deck = sample_deck()
        deck["slides"][1]["bullets"] = ["样本内 MAU 份额：豆包 49.9%、千问 21.9%"]
        deck["slides"][1]["source_ids"] = ["src_1"]
        deck["slides"][1]["chart"] = {
            "type": "bar",
            "title": "样本内 MAU 份额",
            "unit": "%",
            "categories": ["豆包", "千问"],
            "series": [{"name": "样本内 MAU 份额", "values": [49.9, 21.9]}],
        }
        issue_types = {
            item["type"] for item in check_deck(deck, {"src_1"}, config) if item["slide_id"] == "s2"
        }
        self.assertNotIn("chart_missing", issue_types)
        self.assertNotIn("invalid_chart", issue_types)


if __name__ == "__main__":
    unittest.main()
