"""定义跨阶段共享的数据契约和严格 JSON Schema。首次使用：S1。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ContractError(ValueError):
    """表示模型输出或工具参数未满足数据契约。首次使用：S1。"""


# 契约层拥有的版式词表；渲染实现在 tools/presentation.py，由测试保证两者一致。
KNOWN_LAYOUTS = ("bullets", "two_column", "comparison_table", "chart_focus", "custom")
DEFAULT_LAYOUT = "bullets"
ELEMENT_TYPES = ("callout", "kpi", "bullets", "chart", "table")
ELEMENT_COLS = (3, 4, 6, 8, 12)
ELEMENT_EMPHASIS = ("low", "medium", "high")


@dataclass(frozen=True)
class ToolCall:
    """表示模型请求执行的一次外部动作。首次使用：S2。"""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """表示一次工具执行后可被模型观察的结果。首次使用：S2。"""

    call_id: str
    name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """将工具结果转换为可以安全写入 JSON 的字典。首次使用：S2。"""

        return asdict(self)


@dataclass
class TaskState:
    """保存经过 runtime 验证的执行事实，而不是模型的口头声明。首次使用：S5。"""

    goal: str
    metric_scope: dict[str, Any]
    selected_products: list[str] = field(default_factory=list)
    # 只有 verified_source_ids 里的来源才经过 read_page 核对，Deck 只能引用这一组；
    # candidate_source_ids 只是搜索结果，让模型能区分“见过”和“可用”。
    verified_source_ids: list[str] = field(default_factory=list)
    candidate_source_ids: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    completed_actions: list[str] = field(default_factory=list)
    current_deck: str | None = None
    current_step: int = 0
    termination_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """将当前任务状态转换为可写入 JSON 的字典。首次使用：S5。"""

        return asdict(self)


@dataclass
class PlanState:
    """保存当前显式计划及其历次修订记录。首次使用：S6。"""

    items: list[dict[str, Any]]
    revision: int = 1
    change_reason: str = "initial plan"
    history: list[dict[str, Any]] = field(default_factory=list)

    def replace(self, items: list[dict[str, Any]], reason: str) -> None:
        """替换当前计划，同时把旧版本和变更原因写入历史。首次使用：S6。"""

        self.history.append(
            {"revision": self.revision, "change_reason": self.change_reason, "items": self.items}
        )
        self.items = items
        self.revision += 1
        self.change_reason = reason

    def to_dict(self) -> dict[str, Any]:
        """将计划及修订历史转换为可写入 JSON 的字典。首次使用：S6。"""

        return asdict(self)


def _string_array_schema() -> dict[str, Any]:
    """生成可复用的严格字符串数组 Schema。首次使用：S1。"""

    return {"type": "array", "items": {"type": "string"}}


def chart_schema() -> dict[str, Any]:
    """生成页面图表数据的严格 Schema；`type=none` 表示本页没有图表。首次使用：S3。"""

    series = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "values": {"type": "array", "items": {"type": "number"}},
        },
        "required": ["name", "values"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["none", "bar", "line"]},
            "title": {"type": "string"},
            "unit": {"type": "string"},
            "categories": _string_array_schema(),
            "series": {"type": "array", "items": series},
        },
        "required": ["type", "title", "unit", "categories", "series"],
        "additionalProperties": False,
    }


def table_schema() -> dict[str, Any]:
    """生成对比表格数据的严格 Schema；`columns` 为空表示本页没有表格。首次使用：S3。"""

    return {
        "type": "object",
        "properties": {
            "caption": {"type": "string"},
            "columns": _string_array_schema(),
            "rows": {"type": "array", "items": _string_array_schema()},
        },
        "required": ["caption", "columns", "rows"],
        "additionalProperties": False,
    }


def element_schema() -> dict[str, Any]:
    """生成页面元素的严格 Schema；`type` 是判别字段，其余字段按类型选择性使用。首次使用：S3。"""

    return {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": list(ELEMENT_TYPES)},
            "cols": {"type": "integer", "enum": list(ELEMENT_COLS)},
            "emphasis": {"type": "string", "enum": list(ELEMENT_EMPHASIS)},
            "text": {"type": "string"},
            "value": {"type": "string"},
            "label": {"type": "string"},
            "items": _string_array_schema(),
            "chart": chart_schema(),
            "table": table_schema(),
        },
        "required": [
            "type",
            "cols",
            "emphasis",
            "text",
            "value",
            "label",
            "items",
            "chart",
            "table",
        ],
        "additionalProperties": False,
    }


def elements_schema() -> dict[str, Any]:
    """生成页面元素列表的 Schema；空数组表示本页不使用自定义布局。首次使用：S3。"""

    return {"type": "array", "items": element_schema()}


def deck_schema(slide_count: int = 5, layouts: list[str] | None = None) -> dict[str, Any]:
    """生成模型输出和 PPT 工具共用的严格 `DeckSpec` Schema。首次使用：S1。"""

    layout_values = list(layouts) if layouts else [DEFAULT_LAYOUT]
    slide = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "layout": {"type": "string", "enum": layout_values},
            "bullets": _string_array_schema(),
            "table": table_schema(),
            "elements": elements_schema(),
            "source_ids": _string_array_schema(),
            "speaker_notes": {"type": "string"},
            "chart": chart_schema(),
        },
        "required": [
            "id",
            "title",
            "layout",
            "bullets",
            "table",
            "elements",
            "source_ids",
            "speaker_notes",
            "chart",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "slides": {
                "type": "array",
                "items": slide,
                "minItems": slide_count,
                "maxItems": slide_count,
            },
        },
        "required": ["title", "slides"],
        "additionalProperties": False,
    }


def product_selection_schema() -> dict[str, Any]:
    """生成候选产品选择结果的 Schema。首次使用：S3。"""

    return {
        "type": "object",
        "properties": {
            "products": _string_array_schema(),
            "selection_reason": {"type": "string"},
        },
        "required": ["products", "selection_reason"],
        "additionalProperties": False,
    }


def evidence_bundle_schema() -> dict[str, Any]:
    """生成带来源、已标准化 Evidence 集合的 Schema。首次使用：S3。"""

    evidence = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "claim": {"type": "string"},
            "product": {"type": "string"},
            "metric": {"type": "string"},
            "value": {"type": "string"},
            "unit": {"type": "string"},
            "period": {"type": "string"},
            "geography": {"type": "string"},
            "platform": {"type": "string"},
            "source_id": {"type": "string"},
            "quote": {"type": "string"},
        },
        "required": [
            "id",
            "claim",
            "product",
            "metric",
            "value",
            "unit",
            "period",
            "geography",
            "platform",
            "source_id",
            "quote",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "evidence": {"type": "array", "items": evidence},
            "open_questions": _string_array_schema(),
        },
        "required": ["evidence", "open_questions"],
        "additionalProperties": False,
    }


def plan_schema() -> dict[str, Any]:
    """生成包含步骤依赖关系的显式计划 Schema。首次使用：S6。"""

    item = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "objective": {"type": "string"},
            "depends_on": _string_array_schema(),
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed", "blocked"]},
            "required_evidence": {"type": "string"},
        },
        "required": ["id", "objective", "depends_on", "status", "required_evidence"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item, "minItems": 1}},
        "required": ["items"],
        "additionalProperties": False,
    }


def deck_patch_schema(layouts: list[str] | None = None) -> dict[str, Any]:
    """生成评审修订时使用的整页替换 Schema。首次使用：S7。"""

    layout_values = list(layouts) if layouts else [DEFAULT_LAYOUT]
    patch = {
        "type": "object",
        "properties": {
            "slide_id": {"type": "string"},
            "title": {"type": "string"},
            "layout": {"type": "string", "enum": layout_values},
            "bullets": _string_array_schema(),
            "table": table_schema(),
            "elements": elements_schema(),
            "source_ids": _string_array_schema(),
            "speaker_notes": {"type": "string"},
            "chart": chart_schema(),
            "reason": {"type": "string"},
            "issue_ids": _string_array_schema(),
        },
        "required": [
            "slide_id",
            "title",
            "layout",
            "bullets",
            "table",
            "elements",
            "source_ids",
            "speaker_notes",
            "chart",
            "reason",
            "issue_ids",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"patches": {"type": "array", "items": patch, "minItems": 1}},
        "required": ["patches"],
        "additionalProperties": False,
    }


def review_issue_schema(max_issues: int = 5) -> dict[str, Any]:
    """生成模型评审产出的 Issue 列表 Schema。首次使用：S7。"""

    issue = {
        "type": "object",
        "properties": {
            "slide_id": {"type": "string"},
            "type": {
                "type": "string",
                "enum": ["content_gap", "contradiction", "off_outline", "clarity", "structure"],
            },
            "severity": {"type": "string", "enum": ["warning"]},
            "evidence": {"type": "string"},
            "suggestion": {"type": "string"},
        },
        "required": ["slide_id", "type", "severity", "evidence", "suggestion"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"issues": {"type": "array", "items": issue, "maxItems": max_issues}},
        "required": ["issues"],
        "additionalProperties": False,
    }


def validate_deck(
    deck: dict[str, Any],
    slide_count: int = 5,
    layouts: list[str] | None = None,
) -> dict[str, Any]:
    """检查页数、页面 ID 和字段类型等稳定生成所需约束。首次使用：S1。"""

    if not isinstance(deck, dict) or not isinstance(deck.get("title"), str):
        raise ContractError("DeckSpec.title 必须是字符串")
    slides = deck.get("slides")
    if not isinstance(slides, list) or len(slides) != slide_count:
        raise ContractError(f"DeckSpec.slides 必须恰好包含 {slide_count} 页")
    expected_ids = [f"s{index}" for index in range(1, slide_count + 1)]
    actual_ids: list[str] = []
    allowed_layouts = set(layouts) if layouts else set(KNOWN_LAYOUTS)
    required = {
        "id",
        "title",
        "layout",
        "bullets",
        "table",
        "elements",
        "source_ids",
        "speaker_notes",
        "chart",
    }
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or not required.issubset(slide):
            raise ContractError(f"第 {index} 页缺少必需字段：{sorted(required - set(slide or {}))}")
        unknown = sorted(set(slide) - required)
        if unknown:
            raise ContractError(f"第 {index} 页包含未知字段：{unknown}")
        if not all(isinstance(slide[key], str) for key in ("id", "title", "speaker_notes")):
            raise ContractError(f"第 {index} 页 id/title/speaker_notes 必须是字符串")
        if slide["layout"] not in allowed_layouts:
            raise ContractError(
                f"第 {index} 页 layout 必须是 {sorted(allowed_layouts)} 之一，当前为 `{slide['layout']}`"
            )
        if not all(
            isinstance(slide[key], list) and all(isinstance(item, str) for item in slide[key])
            for key in ("bullets", "source_ids")
        ):
            raise ContractError(f"第 {index} 页 bullets/source_ids 必须是字符串数组")
        _validate_chart(slide["chart"], index)
        _validate_table(slide["table"], index)
        _validate_elements(slide["elements"], index)
        actual_ids.append(slide["id"])
    if actual_ids != expected_ids:
        raise ContractError(f"页面 ID 必须依次为 {expected_ids}")
    return deck


def _validate_elements(elements: Any, page_index: int) -> None:
    """校验页面元素列表的结构，以及每种元素所需字段是否已填充。首次使用：S3。"""

    if not isinstance(elements, list):
        raise ContractError(f"第 {page_index} 页 elements 必须是数组")
    for element_index, element in enumerate(elements):
        if not isinstance(element, dict) or set(element) != {
            "type",
            "cols",
            "emphasis",
            "text",
            "value",
            "label",
            "items",
            "chart",
            "table",
        }:
            raise ContractError(f"第 {page_index} 页第 {element_index + 1} 个元素字段不完整")
        element_type = element["type"]
        if element_type not in ELEMENT_TYPES:
            raise ContractError(f"第 {page_index} 页元素 type 必须是 {ELEMENT_TYPES} 之一")
        if element["cols"] not in ELEMENT_COLS:
            raise ContractError(f"第 {page_index} 页元素 cols 必须是 {ELEMENT_COLS} 之一")
        if element["emphasis"] not in ELEMENT_EMPHASIS:
            raise ContractError(f"第 {page_index} 页元素 emphasis 必须是 {ELEMENT_EMPHASIS} 之一")
        if element_type == "callout" and not element["text"].strip():
            raise ContractError(f"第 {page_index} 页 callout 元素缺少 text")
        if element_type == "kpi" and not element["value"].strip():
            raise ContractError(f"第 {page_index} 页 kpi 元素缺少 value")
        if element_type == "bullets" and not element["items"]:
            raise ContractError(f"第 {page_index} 页 bullets 元素缺少 items")
        if element_type == "chart" and (
            element["chart"].get("type") == "none"
            or not element["chart"].get("categories")
            or not element["chart"].get("series")
        ):
            raise ContractError(f"第 {page_index} 页 chart 元素缺少有效图表数据")
        if element_type == "table" and (
            not element["table"].get("columns") or not element["table"].get("rows")
        ):
            raise ContractError(f"第 {page_index} 页 table 元素缺少有效表格数据")


def _validate_table(table: Any, page_index: int) -> None:
    """校验对比表格字段的类型与行列一致性。首次使用：S3。"""

    fields = {"caption", "columns", "rows"}
    if not isinstance(table, dict) or set(table) != fields:
        raise ContractError(f"第 {page_index} 页 table 字段必须恰好为 {sorted(fields)}")
    if not isinstance(table["caption"], str):
        raise ContractError(f"第 {page_index} 页 table.caption 必须是字符串")
    columns = table["columns"]
    if not isinstance(columns, list) or not all(isinstance(item, str) for item in columns):
        raise ContractError(f"第 {page_index} 页 table.columns 必须是字符串数组")
    rows = table["rows"]
    if not isinstance(rows, list) or not all(
        isinstance(row, list) and all(isinstance(cell, str) for cell in row) for row in rows
    ):
        raise ContractError(f"第 {page_index} 页 table.rows 必须是字符串二维数组")
    if not columns and rows:
        raise ContractError(f"第 {page_index} 页 table 有数据行却没有 columns")
    for row in rows:
        if len(row) != len(columns):
            raise ContractError(f"第 {page_index} 页 table 每行单元格数必须与 columns 一致")


def _validate_chart(chart: Any, page_index: int) -> None:
    """校验页面图表字段的类型与内部一致性。首次使用：S3。"""

    fields = {"type", "title", "unit", "categories", "series"}
    if not isinstance(chart, dict) or set(chart) != fields:
        raise ContractError(f"第 {page_index} 页 chart 字段必须恰好为 {sorted(fields)}")
    chart_type = chart["type"]
    if chart_type not in {"none", "bar", "line"}:
        raise ContractError(f"第 {page_index} 页 chart.type 必须是 none/bar/line")
    if not isinstance(chart["title"], str) or not isinstance(chart["unit"], str):
        raise ContractError(f"第 {page_index} 页 chart.title/unit 必须是字符串")
    categories = chart["categories"]
    if not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
        raise ContractError(f"第 {page_index} 页 chart.categories 必须是字符串数组")
    series = chart["series"]
    if not isinstance(series, list):
        raise ContractError(f"第 {page_index} 页 chart.series 必须是数组")
    for item in series:
        if not isinstance(item, dict) or set(item) != {"name", "values"}:
            raise ContractError(f"第 {page_index} 页 chart.series 每项必须恰好含 name/values")
        if not isinstance(item["name"], str):
            raise ContractError(f"第 {page_index} 页 chart.series[].name 必须是字符串")
        values = item["values"]
        if not isinstance(values, list) or not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) for value in values
        ):
            raise ContractError(f"第 {page_index} 页 chart.series[].values 必须是数值数组")
    if chart_type == "none":
        return
    # 有图时数据必须自洽：不能缺分类、缺序列，或长度对不上。
    if not categories:
        raise ContractError(f"第 {page_index} 页图表缺少 categories")
    if not series:
        raise ContractError(f"第 {page_index} 页图表缺少 series")
    for item in series:
        if len(item["values"]) != len(categories):
            raise ContractError(
                f"第 {page_index} 页图表 series `{item['name']}` 的数值个数与 categories 不一致"
            )


def validate_products(products: list[Any], minimum: int, maximum: int) -> list[str]:
    """检查模型选择的产品数量、非空性和唯一性。首次使用：S3。"""

    if not all(isinstance(item, str) and item.strip() for item in products):
        raise ContractError("候选产品必须是非空字符串")
    normalized = list(dict.fromkeys(item.strip() for item in products))
    if not minimum <= len(normalized) <= maximum:
        raise ContractError(f"候选产品数量必须在 {minimum}–{maximum} 之间")
    return normalized


def evidence_is_comparable(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """在制作图表前确定性比较两条证据的指标口径。首次使用：S3。"""

    keys = ("metric", "geography", "platform", "unit")
    return all(str(left.get(key, "")).strip() == str(right.get(key, "")).strip() for key in keys)


def apply_deck_patches(deck: dict[str, Any], patch_data: dict[str, Any]) -> dict[str, Any]:
    """根据稳定页面 ID 应用已经校验的整页替换。首次使用：S7。"""

    slides = {slide["id"]: dict(slide) for slide in deck["slides"]}
    for patch in patch_data.get("patches", []):
        slide_id = patch.get("slide_id")
        if slide_id not in slides:
            raise ContractError(f"DeckPatch 引用了未知页面：{slide_id}")
        slides[slide_id] = {
            "id": slide_id,
            "title": patch["title"],
            "layout": patch["layout"],
            "bullets": patch["bullets"],
            "table": patch["table"],
            "elements": patch["elements"],
            "source_ids": patch["source_ids"],
            "speaker_notes": patch["speaker_notes"],
            "chart": patch["chart"],
        }
    revised = {"title": deck["title"], "slides": [slides[f"s{i}"] for i in range(1, len(slides) + 1)]}
    return validate_deck(revised, len(deck["slides"]))
