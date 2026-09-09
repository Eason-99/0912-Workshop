"""对 DeckSpec 内容和 PPT 元素边界执行确定性检查。首次使用：S7。"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from core.config import AppConfig


NUMERIC_PATTERN = re.compile(r"\d+(?:[.,]\d+)?(?:万|亿|%|人|次)?")


def _issue(
    issue_id: str,
    slide_id: str,
    issue_type: str,
    severity: str,
    evidence: str,
    suggestion: str,
) -> dict[str, str]:
    """构造一条字段稳定的 `ReviewIssue`。首次使用：S7。"""

    return {
        "id": issue_id,
        "slide_id": slide_id,
        "type": issue_type,
        "severity": severity,
        "evidence": evidence,
        "suggestion": suggestion,
    }


def check_deck(
    deck: dict[str, Any],
    known_source_ids: set[str],
    config: AppConfig,
    pptx_path: Path | None = None,
) -> list[dict[str, str]]:
    """检查文字密度、指标标签、来源引用和可选的 PPT 边界。首次使用：S7。"""

    review = config.section("review")
    max_bullets = int(review.get("max_bullets_per_slide", 6))
    max_chars = int(review.get("max_chars_per_slide", 260))
    issues: list[dict[str, str]] = []
    counter = 1
    for slide in deck["slides"]:
        slide_id = slide["id"]
        if len(slide["bullets"]) > max_bullets:
            issues.append(
                _issue(f"issue_{counter}", slide_id, "too_many_bullets", "warning", str(len(slide["bullets"])), f"不超过 {max_bullets} 条")
            )
            counter += 1
        char_count = sum(len(item) for item in slide["bullets"])
        if char_count > max_chars:
            issues.append(
                _issue(f"issue_{counter}", slide_id, "too_much_text", "warning", str(char_count), f"压缩到 {max_chars} 字以内")
            )
            counter += 1
        unknown = sorted(set(slide["source_ids"]) - known_source_ids)
        if unknown:
            issues.append(
                _issue(f"issue_{counter}", slide_id, "unknown_source", "error", ", ".join(unknown), "删除或替换未知来源 ID")
            )
            counter += 1
        joined = " ".join(slide["bullets"])
        if review.get("require_source_for_numeric_claim", True) and NUMERIC_PATTERN.search(joined) and not slide["source_ids"]:
            issues.append(
                _issue(f"issue_{counter}", slide_id, "numeric_claim_without_source", "error", joined[:160], "为数字添加已读取来源，或删除无依据数字")
            )
            counter += 1
        if (
            review.get("require_metric_scope_label", True)
            and slide_id == "s2"
            and "份额" in joined
            and "样本内 MAU 份额" not in joined
        ):
            issues.append(
                _issue(f"issue_{counter}", slide_id, "share_label", "error", "份额标签不完整", "统一写为“样本内 MAU 份额”")
            )
            counter += 1
    if pptx_path and pptx_path.exists():
        for bounds_issue in check_ppt_bounds(pptx_path, counter):
            issues.append(bounds_issue)
            counter += 1
    return issues


def check_ppt_bounds(pptx_path: Path, starting_counter: int = 1) -> list[dict[str, str]]:
    """标记超出幻灯片物理画布边界的元素。首次使用：S7。"""

    try:
        from pptx import Presentation
    except ImportError:
        return [
            _issue(
                f"issue_{starting_counter}",
                "deck",
                "dependency_missing",
                "warning",
                "python-pptx unavailable",
                "安装 src/requirements.txt 后重新检查",
            )
        ]
    prs = Presentation(str(pptx_path))
    issues: list[dict[str, str]] = []
    counter = starting_counter
    for page_number, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.left < 0 or shape.top < 0 or shape.left + shape.width > prs.slide_width or shape.top + shape.height > prs.slide_height:
                issues.append(
                    _issue(
                        f"issue_{counter}",
                        f"s{page_number}",
                        "shape_out_of_bounds",
                        "error",
                        getattr(shape, "name", "unknown shape"),
                        "缩小或移动该元素",
                    )
                )
                counter += 1
    return issues
