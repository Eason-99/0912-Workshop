"""实现 PPT 构建、渲染和结构化页面修订。首次使用：S2。"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Any

from core.config import AppConfig
from core.contracts import apply_deck_patches, validate_deck


class PresentationToolError(RuntimeError):
    """表示需要作为 Observation 返回的演示文稿工具错误。首次使用：S2。"""


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

    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    frame = box.text_frame
    frame.clear()
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.name = font_name
    paragraph.font.size = Pt(font_size)
    paragraph.font.bold = bold


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

    for page_number, slide_data in enumerate(deck["slides"], start=1):
        slide = prs.slides.add_slide(blank_layout)
        _add_textbox(slide, slide_data["title"], 0.7, 0.45, 11.7, 0.75, font_name, 26, True)
        bullet_text = "\n".join(f"• {item}" for item in slide_data["bullets"])
        _add_textbox(slide, bullet_text, 0.9, 1.45, 11.5, 4.9, font_name, 18)
        source_text = "来源：" + ("；".join(slide_data["source_ids"]) or "本页无外部来源")
        _add_textbox(slide, source_text, 0.7, 6.72, 11.6, 0.35, font_name, 9)
        _add_textbox(slide, str(page_number), 12.45, 6.72, 0.3, 0.3, font_name, 9)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))
    return {"pptx_path": str(output_path), "slide_count": len(prs.slides)}


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
