"""实现 PPT 构建、渲染和结构化页面修订。首次使用：S2。"""

from __future__ import annotations

from pathlib import Path
import math
import shutil
import subprocess
from typing import Any

from core.config import AppConfig
from core.contracts import apply_deck_patches, validate_deck


class PresentationToolError(RuntimeError):
    """表示需要作为 Observation 返回的演示文稿工具错误。首次使用：S2。"""


# 全角字符从此码位开始，按 1 个宽度单位估算；半角按 0.55 估算。
FULL_WIDTH_THRESHOLD = 0x2E80
# 单行实际高度约为字号的倍数，用于把行数换算成需要的英寸高度。
LINE_SPACING = 1.25


def _text_width_units(text: str) -> float:
    """估算文本的显示宽度单位，用于预测自动换行后的行数。首次使用：S2。"""

    return sum(1.0 if ord(char) >= FULL_WIDTH_THRESHOLD else 0.55 for char in text)


def _estimate_line_count(text: str, width_inches: float, font_size: int) -> int:
    """按框宽估算自动换行后的行数；每个换行符单独起一行。首次使用：S2。"""

    capacity = max(4.0, (width_inches * 72.0) / float(font_size))
    return sum(
        max(1, math.ceil(_text_width_units(segment) / capacity)) for segment in text.split("\n")
    )


def _fit_font_size(
    text: str,
    width_inches: float,
    height_inches: float,
    preferred_size: int,
    minimum_size: int,
) -> int:
    """从首选字号逐磅下调，直到文本能放进文本框为止。首次使用：S2。"""

    for size in range(preferred_size, minimum_size - 1, -1):
        needed = _estimate_line_count(text, width_inches, size) * size * LINE_SPACING / 72.0
        if needed <= height_inches:
            return size
    return minimum_size


def _add_textbox(
    slide: Any,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    font_name: str,
    font_size: int,
    bold: bool = False,
) -> None:
    """按照英寸坐标添加样式统一的文本框。首次使用：S2。"""

    from pptx.util import Inches, Pt
    from pptx.enum.text import MSO_AUTO_SIZE

    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    # python-pptx 的 add_textbox() 默认写入 <a:bodyPr wrap="none"><a:spAutoFit/>：
    # 文本不换行，会向右溢出文本框，只有手动微调形状时才重新排版。
    # 这里显式开启自动换行、固定形状尺寸，并把内边距归零，使坐标即文本起点。
    frame.word_wrap = True
    frame.auto_size = MSO_AUTO_SIZE.NONE
    frame.margin_left = 0
    frame.margin_right = 0
    frame.margin_top = 0
    frame.margin_bottom = 0
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.name = font_name
    paragraph.font.size = Pt(font_size)
    paragraph.font.bold = bold


CHART_TYPES = {"bar", "line"}


def _chart_is_renderable(chart: Any) -> bool:
    """判断页面图表是否可以真正渲染出图形。首次使用：S3。"""

    if not isinstance(chart, dict):
        return False
    if str(chart.get("type", "none")) not in CHART_TYPES:
        return False
    return bool(chart.get("categories")) and bool(chart.get("series"))


def _add_chart(
    slide: Any,
    chart_data: dict[str, Any],
    left: float,
    top: float,
    width: float,
    height: float,
    font_name: str,
) -> None:
    """用 python-pptx 原生图表渲染页面数据，保持图表在 PPT 内可编辑。首次使用：S3。"""

    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.util import Inches, Pt

    chart_type = (
        XL_CHART_TYPE.COLUMN_CLUSTERED if chart_data["type"] == "bar" else XL_CHART_TYPE.LINE_MARKERS
    )
    data = CategoryChartData()
    data.categories = list(chart_data["categories"])
    for series in chart_data["series"]:
        data.add_series(str(series["name"]), tuple(series["values"]))
    chart = slide.shapes.add_chart(
        chart_type, Inches(left), Inches(top), Inches(width), Inches(height), data
    ).chart

    title = str(chart_data.get("title", "")).strip()
    chart.has_title = bool(title)
    if title:
        chart.chart_title.text_frame.text = title
        for paragraph in chart.chart_title.text_frame.paragraphs:
            paragraph.font.size = Pt(12)
            paragraph.font.name = font_name

    chart.has_legend = len(chart_data["series"]) > 1
    if chart.has_legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(10)
        chart.legend.font.name = font_name
    chart.font.size = Pt(10)
    chart.font.name = font_name

    unit = str(chart_data.get("unit", "")).strip()
    if unit == "%":
        chart.value_axis.tick_labels.number_format = '0.0"%"'
    if unit:
        try:
            chart.value_axis.has_title = True
            chart.value_axis.axis_title.text_frame.text = unit
            chart.value_axis.axis_title.text_frame.paragraphs[0].font.size = Pt(10)
            chart.value_axis.axis_title.text_frame.paragraphs[0].font.name = font_name
        except (AttributeError, ValueError):
            # 老版本 python-pptx 没有 axis_title，此时只保留坐标轴刻度。
            chart.value_axis.has_title = False


def create_ppt(deck: dict[str, Any], output_path: Path, config: AppConfig) -> dict[str, Any]:
    """把已校验的 `DeckSpec` 转换为简洁可读的 PPTX。首次使用：S2。"""

    try:
        from pptx import Presentation
        from pptx.util import Inches
    except ImportError as exc:
        raise PresentationToolError("缺少 python-pptx；请安装 src/requirements.txt") from exc

    slide_count = int(config.section("task")["slide_count"])
    validate_deck(deck, slide_count)
    presentation_config = config.section("presentation")
    template = config.resolve_path(presentation_config.get("template"))
    if template and not template.exists():
        raise PresentationToolError(f"PPT 模板不存在：{template}")
    prs = Presentation(str(template)) if template else Presentation()
    if len(prs.slides):
        raise PresentationToolError("模板必须是不含现有页面的空白 .pptx")
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    font_name = str(presentation_config.get("font_family", "Noto Sans CJK SC"))
    blank_layout = prs.slide_layouts[6]
    rendered_charts = 0
    shrunk_pages: list[str] = []

    for page_number, slide_data in enumerate(deck["slides"], start=1):
        slide = prs.slides.add_slide(blank_layout)
        title_size = _fit_font_size(slide_data["title"], 11.7, 0.75, 26, 16)
        _add_textbox(slide, slide_data["title"], 0.7, 0.45, 11.7, 0.75, font_name, title_size, True)
        bullet_text = "\n".join(f"• {item}" for item in slide_data["bullets"])
        if _chart_is_renderable(slide_data.get("chart")):
            # 有图时正文让出右半版面，并缩小字号避免与图表重叠。
            bullet_width, bullet_size_preferred = 5.9, 14
            _add_chart(slide, slide_data["chart"], 7.0, 1.5, 5.6, 4.8, font_name)
            rendered_charts += 1
        else:
            bullet_width, bullet_size_preferred = 11.5, 18
        # 换行生效后文字会变高，这里保证它始终落在正文框内，不会压到来源行。
        bullet_size = _fit_font_size(bullet_text, bullet_width, 4.9, bullet_size_preferred, 10)
        if bullet_size != bullet_size_preferred:
            shrunk_pages.append(slide_data["id"])
        _add_textbox(slide, bullet_text, 0.9, 1.45, bullet_width, 4.9, font_name, bullet_size)
        source_text = "来源：" + ("；".join(slide_data["source_ids"]) or "本页无外部来源")
        _add_textbox(slide, source_text, 0.7, 6.72, 11.6, 0.35, font_name, 9)
        _add_textbox(slide, str(page_number), 12.45, 6.72, 0.3, 0.3, font_name, 9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return {
        "pptx_path": str(output_path),
        "slide_count": len(prs.slides),
        "chart_count": rendered_charts,
        "shrunk_font_pages": shrunk_pages,
    }


def render_ppt(pptx_path: Path, output_dir: Path, dpi: int) -> dict[str, Any]:
    """在工具可用时通过 LibreOffice 和 pdftoppm 把 PPT 渲染为图片。首次使用：S7。"""

    libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
    pdftoppm = shutil.which("pdftoppm")
    if not libreoffice or not pdftoppm:
        return {
            "rendered": False,
            "images": [],
            "warning": "未找到 LibreOffice 或 pdftoppm；已降级为结构检查",
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    conversion = subprocess.run(
        [libreoffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx_path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if conversion.returncode != 0:
        raise PresentationToolError(f"LibreOffice 渲染失败：{conversion.stderr.strip()}")
    pdf_path = output_dir / f"{pptx_path.stem}.pdf"
    if not pdf_path.exists():
        raise PresentationToolError("LibreOffice 未生成预期 PDF")
    raster = subprocess.run(
        [pdftoppm, "-png", "-r", str(dpi), str(pdf_path), str(output_dir / "slide")],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if raster.returncode != 0:
        raise PresentationToolError(f"pdftoppm 转图失败：{raster.stderr.strip()}")
    images = sorted(str(path) for path in output_dir.glob("slide-*.png"))
    return {"rendered": True, "pdf_path": str(pdf_path), "images": images}


def patch_deck(deck: dict[str, Any], patch_data: dict[str, Any]) -> dict[str, Any]:
    """在不直接编辑 PPTX 的情况下应用结构化整页修订。首次使用：S7。"""

    return apply_deck_patches(deck, patch_data)
