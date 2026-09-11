
#!/usr/bin/env python3
"""
Agent Workshop 开场页扩展：
在现有 Agent from Scratch PPT 前增加 LLM vs Agent 概念引入。

设计原则：
- 保持当前 PPT 的白底、深蓝标题、蓝/橙/绿色语义。
- main() 只负责调用 build_intro_slides()，方便后续扩展。
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor


OUT = "agent_intro_slides.pptx"


class C:
    NAVY = "17324D"
    BLUE = "315B7D"
    ORANGE = "D97706"
    GREEN = "2F855A"
    RED = "C2413B"
    INK = "263746"
    GRAY = "64748B"
    LIGHT = "E2E8F0"
    PALE = "F4F7FA"
    PALE_BLUE = "EAF1F7"
    PALE_ORANGE = "FFF4E6"
    PALE_GREEN = "EAF6EF"
    WHITE = "FFFFFF"


def rgb(x):
    return RGBColor.from_string(x)


def add_text(slide, text, x, y, w, h, size=20, color=C.INK,
             bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    for r in p.runs:
        r.font.name = "Aptos"
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = rgb(color)
    return box


def add_box(slide, text, x, y, w, h, fill, line, size=18):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.color.rgb = rgb(line)

    add_text(slide, text, x + 0.08, y + 0.05,
             w - 0.16, h - 0.1,
             size=size, color=C.NAVY,
             bold=True, align=PP_ALIGN.CENTER)


def add_arrow(slide, x1, y1, x2, y2, color=C.BLUE):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1), Inches(y1),
        Inches(x2), Inches(y2)
    )
    line.line.color.rgb = rgb(color)
    line.line.width = Pt(2)


def new_slide(prs, title):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(C.WHITE)

    add_text(slide, title, 0.7, 0.35, 12, 0.5,
             30, C.NAVY, True)

    slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(0.7), Inches(1.0),
        Inches(12.6), Inches(1.0)
    ).line.color.rgb = rgb(C.LIGHT)

    return slide


def slide_llm(prs):
    slide = new_slide(prs, "LLM: From Text Input to Text Output")

    add_text(slide,
             "LLM = Language Model\nThe interaction interface is language.",
             1.0, 1.35, 11, 0.7,
             22, C.BLUE, True, PP_ALIGN.CENTER)

    add_box(slide, "User Prompt\n(text)", 1.2, 3.0, 2.2, 1.0,
            C.PALE_BLUE, C.BLUE)

    add_box(slide, "LLM\nLanguage Model", 5.0, 3.0, 2.6, 1.0,
            C.PALE_BLUE, C.BLUE)

    add_box(slide, "Response\n(text)", 9.6, 3.0, 2.2, 1.0,
            C.PALE_GREEN, C.GREEN)

    add_arrow(slide, 3.5, 3.5, 5.0, 3.5)
    add_arrow(slide, 7.6, 3.5, 9.6, 3.5)

    add_text(slide,
             "A standalone LLM can generate information,\n"
             "but it cannot directly search, execute code, or modify the world.",
             1.3, 5.0, 10.5, 0.8,
             18, C.GRAY, False, PP_ALIGN.CENTER)


def slide_agent(prs):
    slide = new_slide(prs, "Agent: From Generating Text to Taking Actions")

    add_box(slide, "Goal", 0.9, 3.0, 1.5, 0.8,
            C.PALE_BLUE, C.BLUE)

    add_box(slide, "LLM\nDecision", 3.2, 3.0, 1.8, 0.8,
            C.PALE_BLUE, C.BLUE)

    add_box(slide, "Action", 6.0, 3.0, 1.8, 0.8,
            C.PALE_ORANGE, C.ORANGE)

    add_box(slide,
            "Environment\nTools / APIs / Files",
            9.0, 3.0, 2.5, 0.8,
            C.PALE_ORANGE, C.ORANGE)

    add_arrow(slide, 2.4, 3.4, 3.2, 3.4)
    add_arrow(slide, 5.0, 3.4, 6.0, 3.4)
    add_arrow(slide, 7.8, 3.4, 9.0, 3.4)

    add_text(slide,
             "The key change:\n"
             "model output becomes an executable decision.",
             2.0, 5.0, 9.0, 0.7,
             20, C.NAVY, True, PP_ALIGN.CENTER)


def slide_loop(prs):
    slide = new_slide(prs, "Why an Agent Needs a Loop")

    add_box(slide, "Goal", 1.0, 3.0, 1.5, 0.8,
            C.PALE_BLUE, C.BLUE)
    add_box(slide, "Decide\n(Action)", 3.2, 2.0, 2.0, 0.9,
            C.PALE_BLUE, C.BLUE)
    add_box(slide, "Environment", 7.0, 2.0, 2.0, 0.9,
            C.PALE_ORANGE, C.ORANGE)
    add_box(slide, "Observation", 5.0, 4.5, 2.0, 0.9,
            C.PALE_GREEN, C.GREEN)

    add_arrow(slide, 2.5, 3.4, 3.2, 2.5)
    add_arrow(slide, 5.2, 2.45, 7.0, 2.45)
    add_arrow(slide, 7.9, 3.0, 6.0, 4.5, C.GREEN)
    add_arrow(slide, 5.0, 4.9, 4.0, 3.0, C.GREEN)

    add_text(slide,
             "Agent = Action + Feedback\n"
             "Observation changes the next Action.",
             2.2, 6.0, 9, 0.5,
             20, C.GREEN, True, PP_ALIGN.CENTER)


def build_intro_slides():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide_llm(prs)
    slide_agent(prs)
    slide_loop(prs)

    prs.save(OUT)


def main():
    build_intro_slides()


if __name__ == "__main__":
    main()
