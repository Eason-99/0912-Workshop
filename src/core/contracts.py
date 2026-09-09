"""定义跨阶段共享的数据契约和严格 JSON Schema。首次使用：S1。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ContractError(ValueError):
    """表示模型输出或工具参数未满足数据契约。首次使用：S1。"""


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
    source_ids: list[str] = field(default_factory=list)
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


def deck_schema(slide_count: int = 5) -> dict[str, Any]:
    """生成模型输出和 PPT 工具共用的严格 `DeckSpec` Schema。首次使用：S1。"""

    slide = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "bullets": _string_array_schema(),
            "source_ids": _string_array_schema(),
            "speaker_notes": {"type": "string"},
        },
        "required": ["id", "title", "bullets", "source_ids", "speaker_notes"],
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


def deck_patch_schema() -> dict[str, Any]:
    """生成评审修订时使用的整页替换 Schema。首次使用：S7。"""

    patch = {
        "type": "object",
        "properties": {
            "slide_id": {"type": "string"},
            "title": {"type": "string"},
            "bullets": _string_array_schema(),
            "source_ids": _string_array_schema(),
            "speaker_notes": {"type": "string"},
            "reason": {"type": "string"},
            "issue_ids": _string_array_schema(),
        },
        "required": [
            "slide_id",
            "title",
            "bullets",
            "source_ids",
            "speaker_notes",
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


def validate_deck(deck: dict[str, Any], slide_count: int = 5) -> dict[str, Any]:
    """检查页数、页面 ID 和字段类型等稳定生成所需约束。首次使用：S1。"""

    if not isinstance(deck, dict) or not isinstance(deck.get("title"), str):
        raise ContractError("DeckSpec.title 必须是字符串")
    slides = deck.get("slides")
    if not isinstance(slides, list) or len(slides) != slide_count:
        raise ContractError(f"DeckSpec.slides 必须恰好包含 {slide_count} 页")
    expected_ids = [f"s{index}" for index in range(1, slide_count + 1)]
    actual_ids: list[str] = []
    required = {"id", "title", "bullets", "source_ids", "speaker_notes"}
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict) or set(slide) != required:
            raise ContractError(f"第 {index} 页字段必须恰好为 {sorted(required)}")
        if not all(isinstance(slide[key], str) for key in ("id", "title", "speaker_notes")):
            raise ContractError(f"第 {index} 页 id/title/speaker_notes 必须是字符串")
        if not all(
            isinstance(slide[key], list) and all(isinstance(item, str) for item in slide[key])
            for key in ("bullets", "source_ids")
        ):
            raise ContractError(f"第 {index} 页 bullets/source_ids 必须是字符串数组")
        actual_ids.append(slide["id"])
    if actual_ids != expected_ids:
        raise ContractError(f"页面 ID 必须依次为 {expected_ids}")
    return deck


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
            "bullets": patch["bullets"],
            "source_ids": patch["source_ids"],
            "speaker_notes": patch["speaker_notes"],
        }
    revised = {"title": deck["title"], "slides": [slides[f"s{i}"] for i in range(1, len(slides) + 1)]}
    return validate_deck(revised, len(deck["slides"]))
