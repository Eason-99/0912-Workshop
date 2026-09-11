"""测试 PPTX 渲染是否满足排版约定。首次覆盖：S2。"""

from pathlib import Path
import tempfile
import unittest
import zipfile

from core.config import load_config
from core.contracts import KNOWN_LAYOUTS
from tests.test_contracts import sample_deck
from tools.presentation import LAYOUT_RENDERERS, create_ppt


class PresentationTests(unittest.TestCase):
    """在不联网、不调用模型的条件下验证 PPTX 输出。首次覆盖：S2。"""

    def _render(self, deck: dict) -> tuple[Path, list[str]]:
        """渲染 Deck 并返回文件路径与该文件内所有 bodyPr 片段。首次覆盖：S2。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        directory = Path(tempfile.mkdtemp())
        output = directory / "deck.pptx"
        create_ppt(deck, output, config)
        with zipfile.ZipFile(output) as archive:
            body_pr = [
                line
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                for line in archive.read(name).decode("utf-8").split("<a:bodyPr")
                if line.startswith((" ", ">", ' wrap', ' autofit'))
            ]
        return output, body_pr

    def test_textboxes_wrap_instead_of_overflowing(self) -> None:
        """确认文本框开启自动换行且不再使用随文字改变形状的 spAutoFit。首次覆盖：S2。"""

        deck = sample_deck()
        deck["slides"][0]["bullets"] = ["这一行文字故意写得很长，用来确认文本框会换行而不是向右溢出边界。"] * 3
        _, body_pr = self._render(deck)
        self.assertTrue(body_pr, "未找到任何文本框")
        for fragment in body_pr:
            self.assertIn('wrap="square"', fragment)
            self.assertNotIn("spAutoFit", fragment)

    def test_chart_is_embedded_as_native_shape(self) -> None:
        """确认带 chart 的页面会嵌入原生图表形状。首次覆盖：S3。"""

        from pptx import Presentation

        deck = sample_deck()
        deck["slides"][1]["chart"] = {
            "type": "bar",
            "title": "样本内 MAU 份额",
            "unit": "%",
            "categories": ["豆包", "千问"],
            "series": [{"name": "样本内 MAU 份额", "values": [51.9, 22.7]}],
        }
        output, _ = self._render(deck)
        slides = list(Presentation(str(output)).slides)
        charts = [shape for shape in slides[1].shapes if getattr(shape, "has_chart", False)]
        plain = [shape for shape in slides[0].shapes if getattr(shape, "has_chart", False)]
        self.assertEqual(len(charts), 1)
        self.assertEqual(len(plain), 0)

    def _body_font_size(self, output: Path, page_index: int) -> float:
        """读取指定页正文文本框的字号。首次覆盖：S2。"""

        from pptx import Presentation

        slide = list(Presentation(str(output)).slides)[page_index]
        body = [
            shape
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.startswith("•")
        ]
        self.assertEqual(len(body), 1)
        return body[0].text_frame.paragraphs[0].font.size.pt

    def test_sparse_slide_keeps_preferred_font_size(self) -> None:
        """确认文字不多的页面保持首选字号，不无故缩小。首次覆盖：S2。"""

        output, _ = self._render(sample_deck())
        self.assertEqual(self._body_font_size(output, 0), 18)

    def test_dense_slide_shrinks_font_to_stay_inside_box(self) -> None:
        """确认文字过多时自动缩小字号，避免溢出正文框。首次覆盖：S2。"""

        deck = sample_deck()
        deck["slides"][0]["bullets"] = ["很长的中文句子" * 120]
        output, _ = self._render(deck)
        self.assertLess(self._body_font_size(output, 0), 18)

    def test_every_known_layout_has_a_renderer(self) -> None:
        """确认契约层词表与渲染分派表保持同步。首次覆盖：S3。"""

        self.assertEqual(set(KNOWN_LAYOUTS), set(LAYOUT_RENDERERS))

    def test_fixed_mode_only_offers_bullets(self) -> None:
        """确认 fixed 模式只提供 bullets，adaptive 模式按配置放开。首次覆盖：S3。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        # 两种模式都显式设置，不依赖仓库当前选的是哪一种。
        config.data["presentation"]["layout_mode"] = "fixed"
        self.assertEqual(config.layout_catalog(), ["bullets"])
        config.data["presentation"]["layout_mode"] = "adaptive"
        # adaptive 目录直接来自配置，这里读回配置而不是写死，避免将来加版式又失效。
        self.assertEqual(
            config.layout_catalog(),
            [str(item) for item in config.section("presentation")["layouts"]],
        )

    def test_comparison_table_layout_embeds_native_table(self) -> None:
        """确认表格版式会生成原生表格，且不要求图表。首次覆盖：S3。"""

        from pptx import Presentation

        deck = sample_deck()
        deck["slides"][1]["layout"] = "comparison_table"
        deck["slides"][1]["table"] = {
            "caption": "样本内 MAU 份额（2026-06）",
            "columns": ["产品", "MAU", "样本内 MAU 份额"],
            "rows": [["豆包", "3.82 亿", "49.0%"], ["千问", "1.67 亿", "21.9%"]],
        }
        output, _ = self._render(deck)
        shapes = list(Presentation(str(output)).slides)[1].shapes
        tables = [shape for shape in shapes if getattr(shape, "has_table", False)]
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0].table.rows), 3)
        self.assertEqual(len(tables[0].table.columns), 3)

    def test_two_column_layout_uses_both_halves(self) -> None:
        """确认两栏版式会生成左右两个正文框。首次覆盖：S3。"""

        from pptx import Presentation

        deck = sample_deck()
        deck["slides"][0]["layout"] = "two_column"
        deck["slides"][0]["bullets"] = ["左一", "左二", "右一", "右二"]
        output, _ = self._render(deck)
        boxes = [
            shape
            for shape in list(Presentation(str(output)).slides)[0].shapes
            if shape.has_text_frame and shape.text_frame.text.startswith("•")
        ]
        self.assertEqual(len(boxes), 2)
        self.assertLess(boxes[0].left, boxes[1].left)

    def test_theme_switch_changes_font_size(self) -> None:
        """确认切换主题会改变正文字号。首次覆盖：S3。"""

        config = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
        deck = sample_deck()
        directory = Path(tempfile.mkdtemp())
        classic = directory / "classic.pptx"
        compact = directory / "compact.pptx"
        create_ppt(deck, classic, config)
        config.data["presentation"]["theme"] = "compact"
        create_ppt(deck, compact, config)
        self.assertEqual(self._body_font_size(classic, 0), 18)
        self.assertEqual(self._body_font_size(compact, 0), 16)

    def test_custom_layout_renders_elements(self) -> None:
        """确认 custom 版式会按元素列表渲染多个小框。首次覆盖：S3。"""

        from pptx import Presentation

        no_chart = {"type": "none", "title": "", "unit": "", "categories": [], "series": []}
        no_table = {"caption": "", "columns": [], "rows": []}
        deck = sample_deck()
        deck["slides"][0]["layout"] = "custom"
        deck["slides"][0]["elements"] = [
            {
                "type": "callout",
                "cols": 12,
                "emphasis": "high",
                "text": "头部集中度持续上升",
                "value": "",
                "label": "",
                "items": [],
                "chart": dict(no_chart),
                "table": dict(no_table),
            },
            {
                "type": "kpi",
                "cols": 4,
                "emphasis": "high",
                "text": "",
                "value": "3.82 亿",
                "label": "豆包 MAU",
                "items": [],
                "chart": dict(no_chart),
                "table": dict(no_table),
            },
            {
                "type": "kpi",
                "cols": 4,
                "emphasis": "medium",
                "text": "",
                "value": "+172%",
                "label": "同比",
                "items": [],
                "chart": dict(no_chart),
                "table": dict(no_table),
            },
            {
                "type": "kpi",
                "cols": 4,
                "emphasis": "medium",
                "text": "",
                "value": "4.99 亿",
                "label": "市场总量",
                "items": [],
                "chart": dict(no_chart),
                "table": dict(no_table),
            },
        ]
        output, _ = self._render(deck)
        shapes = list(Presentation(str(output)).slides)[0].shapes
        rectangles = [shape for shape in shapes if getattr(shape, "shape_type", None) is not None and shape.shape_type == 1]
        texts = [shape for shape in shapes if shape.has_text_frame and shape.text_frame.text]
        self.assertEqual(len(rectangles), 1)  # callout 的强调色条
        self.assertGreaterEqual(len(texts), 4)  # 标题 + callout + 3 个 kpi（value/label 分开）


if __name__ == "__main__":
    unittest.main()
