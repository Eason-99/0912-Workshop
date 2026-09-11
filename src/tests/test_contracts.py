"""测试 Deck、Evidence 和 Patch 等数据契约。首次覆盖：S1。"""

import unittest

from core.contracts import ContractError, apply_deck_patches, evidence_is_comparable, validate_deck
from stages.common import build_comparability_report


def sample_deck() -> dict:
    """构造合法的五页最小 Deck 测试夹具（含空图表与空表格）。首次覆盖：S1。"""

    no_chart = {"type": "none", "title": "", "unit": "", "categories": [], "series": []}
    no_table = {"caption": "", "columns": [], "rows": []}
    return {
        "title": "测试 Deck",
        "slides": [
            {
                "id": f"s{index}",
                "title": f"第 {index} 页",
                "layout": "bullets",
                "bullets": ["测试内容"],
                "table": dict(no_table),
                "elements": [],
                "source_ids": [],
                "speaker_notes": "",
                "chart": dict(no_chart),
            }
            for index in range(1, 6)
        ],
    }


class ContractTests(unittest.TestCase):
    """校验 DeckSpec 稳定性和 Evidence 口径规则。首次覆盖：S1。"""

    def test_validate_deck_accepts_stable_ids(self) -> None:
        """确认按序使用稳定 ID 的五页 Deck 可以通过。首次覆盖：S1。"""

        self.assertEqual(validate_deck(sample_deck()), sample_deck())

    def test_validate_deck_rejects_wrong_id_order(self) -> None:
        """确认文件生成前会拒绝错误的页面 ID 顺序。首次覆盖：S1。"""

        deck = sample_deck()
        deck["slides"][0]["id"] = "intro"
        with self.assertRaises(ContractError):
            validate_deck(deck)

    def test_evidence_scope_is_deterministic(self) -> None:
        """确认指标口径比较不依赖模型主观判断。首次覆盖：S3。"""

        left = {"metric": "MAU", "geography": "中国大陆", "platform": "移动 App", "unit": "万人"}
        right = dict(left)
        self.assertTrue(evidence_is_comparable(left, right))
        right["metric"] = "DAU"
        self.assertFalse(evidence_is_comparable(left, right))

    def test_comparability_report_groups_and_excludes(self) -> None:
        """确认 Workflow 会分组同口径证据并排除字段缺失项。首次覆盖：S3。"""

        complete = {
            "id": "e1",
            "metric": "MAU",
            "value": "1000",
            "unit": "万人",
            "period": "2026-08",
            "geography": "中国大陆",
            "platform": "移动 App",
        }
        incomplete = {**complete, "id": "e2", "period": ""}
        report = build_comparability_report([complete, incomplete])
        self.assertEqual(report["comparable_groups"][0]["evidence_ids"], ["e1"])
        self.assertEqual(report["excluded"][0]["evidence_id"], "e2")

    def test_patch_replaces_only_target_slide(self) -> None:
        """确认整页 Patch 只替换指定的稳定页面 ID。首次覆盖：S7。"""

        deck = sample_deck()
        revised = apply_deck_patches(
            deck,
            {
                "patches": [
                    {
                        "slide_id": "s2",
                        "title": "修订页",
                        "layout": "bullets",
                        "bullets": ["样本内 MAU 份额"],
                        "table": {"caption": "", "columns": [], "rows": []},
                        "elements": [],
                        "source_ids": [],
                        "speaker_notes": "修订",
                        "chart": {"type": "none", "title": "", "unit": "", "categories": [], "series": []},
                        "reason": "修正标签",
                        "issue_ids": ["issue_1"],
                    }
                ]
            },
        )
        self.assertEqual(revised["slides"][1]["title"], "修订页")
        self.assertEqual(revised["slides"][0], deck["slides"][0])

    def test_validate_deck_rejects_inconsistent_chart(self) -> None:
        """确认图表数值与分类数量不一致时会被拒绝。首次覆盖：S3。"""

        deck = sample_deck()
        deck["slides"][1]["chart"] = {
            "type": "bar",
            "title": "样本内 MAU 份额",
            "unit": "%",
            "categories": ["豆包", "千问"],
            "series": [{"name": "样本内 MAU 份额", "values": [49.9]}],
        }
        with self.assertRaises(ContractError):
            validate_deck(deck)

    def test_validate_deck_accepts_consistent_chart(self) -> None:
        """确认自洽的柱状图可以通过契约校验。首次覆盖：S3。"""

        deck = sample_deck()
        deck["slides"][1]["chart"] = {
            "type": "bar",
            "title": "样本内 MAU 份额",
            "unit": "%",
            "categories": ["豆包", "千问"],
            "series": [{"name": "样本内 MAU 份额", "values": [49.9, 21.9]}],
        }
        self.assertEqual(len(validate_deck(deck)["slides"]), 5)

    def test_validate_deck_restricts_layout_to_catalog(self) -> None:
        """确认版式超出当前模式目录时会被拒绝。首次覆盖：S3。"""

        deck = sample_deck()
        deck["slides"][0]["layout"] = "comparison_table"
        with self.assertRaises(ContractError):
            validate_deck(deck, layouts=["bullets"])
        # 目录放开后同一份 Deck 应通过。
        self.assertEqual(
            len(validate_deck(deck, layouts=["bullets", "comparison_table"])["slides"]), 5
        )

    def test_validate_deck_rejects_inconsistent_table(self) -> None:
        """确认表格行列数不一致时会被拒绝。首次覆盖：S3。"""

        deck = sample_deck()
        deck["slides"][1]["layout"] = "comparison_table"
        deck["slides"][1]["table"] = {
            "caption": "样本内 MAU 份额",
            "columns": ["产品", "份额"],
            "rows": [["豆包", "49.0%", "多余"]],
        }
        with self.assertRaises(ContractError):
            validate_deck(deck)

    def test_validate_deck_rejects_incomplete_element(self) -> None:
        """确认 callout 元素缺少 text 时会被拒绝。首次覆盖：S3。"""

        deck = sample_deck()
        deck["slides"][0]["layout"] = "custom"
        deck["slides"][0]["elements"] = [
            {
                "type": "callout",
                "cols": 12,
                "emphasis": "high",
                "text": "",
                "value": "",
                "label": "",
                "items": [],
                "chart": {"type": "none", "title": "", "unit": "", "categories": [], "series": []},
                "table": {"caption": "", "columns": [], "rows": []},
            }
        ]
        with self.assertRaises(ContractError):
            validate_deck(deck)


if __name__ == "__main__":
    unittest.main()
