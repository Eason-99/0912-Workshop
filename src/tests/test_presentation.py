"""测试 PPTX 渲染是否满足排版约定。首次覆盖：S2。"""

from pathlib import Path
import tempfile
import unittest
import zipfile

from core.config import load_config
from tests.test_contracts import sample_deck
from tools.presentation import create_ppt


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


if __name__ == "__main__":
    unittest.main()
