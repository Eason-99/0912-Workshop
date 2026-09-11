"""读取并校验唯一的 YAML 配置文件，为所有模块提供统一输入。首次使用：S0。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.contracts import DEFAULT_LAYOUT, KNOWN_LAYOUTS


VALID_STAGES = {
    "s0_api",
    "s1_structured",
    "s2_tools",
    "s3_workflow",
    "s4_agent",
    "s5_state",
    "s6_planning",
    "s7_reflection",
}


class ConfigError(ValueError):
    """表示应在模型或工具执行前暴露的配置错误。首次使用：S0。"""


@dataclass(frozen=True)
class AppConfig:
    """封装已校验的配置，并确保文件路径以 `src` 为根目录。首次使用：S0。"""

    data: dict[str, Any]
    config_path: Path
    src_dir: Path

    @property
    def stage(self) -> str:
        """返回 `run.stage` 指定的当前教学阶段。首次使用：S0。"""

        return str(self.data["run"]["stage"])

    def section(self, name: str) -> dict[str, Any]:
        """读取一个必需的顶层配置区块，并检查其类型。首次使用：S0。"""

        value = self.data.get(name)
        if not isinstance(value, dict):
            raise ConfigError(f"配置字段 `{name}` 必须是 mapping")
        return value

    def resolve_path(self, value: str | None) -> Path | None:
        """将相对路径解析到 `src` 下，并拒绝越界路径。首次使用：S0。"""

        if value is None:
            return None
        candidate = (self.src_dir / value).resolve()
        if candidate != self.src_dir and self.src_dir not in candidate.parents:
            raise ConfigError(f"路径必须位于 src 内：{value}")
        return candidate

    def credential(self, section: str, field: str) -> str:
        """根据配置中的环境变量名读取通用凭据。首次使用：S0。"""

        env_name = str(self.section(section).get(field, "")).strip()
        if not env_name:
            raise ConfigError(f"缺少配置字段 `{section}.{field}`")
        value = os.getenv(env_name, "").strip()
        if not value:
            raise ConfigError(f"环境变量 `{env_name}` 未设置")
        return value

    def active_model_profile(self) -> tuple[str, dict[str, Any]]:
        """返回当前选中的模型 profile 名称及其配置。首次使用：S0。"""

        model = self.section("model")
        profile_name = str(model["active_profile"])
        profiles = model["profiles"]
        return profile_name, profiles[profile_name]

    def layout_catalog(self) -> list[str]:
        """返回当前允许的页面版式目录；fixed 模式固定只用 bullets。首次使用：S3。"""

        presentation = self.section("presentation")
        if str(presentation.get("layout_mode", "fixed")).strip() != "adaptive":
            return [DEFAULT_LAYOUT]
        configured = presentation.get("layouts")
        names = [str(item).strip() for item in configured] if isinstance(configured, list) else []
        return [name for name in names if name] or [DEFAULT_LAYOUT]

    def model_connection(self, profile_name: str | None = None) -> tuple[str, str]:
        """从 `.env` 读取指定或当前模型的 API Key 与 Base URL。首次使用：S0。"""

        if profile_name is None:
            profile_name, profile = self.active_model_profile()
        else:
            profiles = self.section("model")["profiles"]
            if profile_name not in profiles:
                raise ConfigError(f"模型 profile 不存在：{profile_name}")
            profile = profiles[profile_name]
        api_key_name = str(profile["api_key_env"])
        base_url_name = str(profile["base_url_env"])
        api_key = os.getenv(api_key_name, "").strip()
        base_url = os.getenv(base_url_name, "").strip().rstrip("/")
        if not api_key:
            raise ConfigError(
                f"模型 profile `{profile_name}` 所需环境变量 `{api_key_name}` 未在 core/.env 中设置"
            )
        if not base_url:
            raise ConfigError(
                f"模型 profile `{profile_name}` 所需环境变量 `{base_url_name}` 未在 core/.env 中设置"
            )
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigError(f"环境变量 `{base_url_name}` 必须是有效的 HTTP(S) Base URL")
        return api_key, base_url


def _require_mapping(data: dict[str, Any], name: str) -> dict[str, Any]:
    """校验并返回指定的顶层 mapping 配置。首次使用：S0。"""

    value = data.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"配置字段 `{name}` 必须是 mapping")
    return value


def _require_positive(mapping: dict[str, Any], field: str, prefix: str) -> int:
    """校验指定配置字段是否为正整数。首次使用：S0。"""

    value = mapping.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigError(f"配置字段 `{prefix}.{field}` 必须是正整数")
    return value


def _resolve_src_path(src_dir: Path, value: Any, field: str) -> Path:
    """把配置路径解析到 `src` 内并返回绝对路径。首次使用：S0。"""

    raw_value = str(value or "").strip()
    if not raw_value:
        raise ConfigError(f"配置字段 `{field}` 不能为空")
    candidate = (src_dir / raw_value).resolve()
    if candidate != src_dir and src_dir not in candidate.parents:
        raise ConfigError(f"`{field}` 必须指向 src 内部")
    return candidate


def _validate_config(data: dict[str, Any], src_dir: Path) -> None:
    """统一校验阶段、任务、限制、服务商以及 `src` 内路径。首次使用：S0。"""

    run = _require_mapping(data, "run")
    stage = run.get("stage")
    if stage not in VALID_STAGES:
        raise ConfigError(f"`run.stage` 必须是 {sorted(VALID_STAGES)} 之一")

    task = _require_mapping(data, "task")
    try:
        date.fromisoformat(str(task.get("data_cutoff_date")))
    except ValueError as exc:
        raise ConfigError("`task.data_cutoff_date` 必须是 YYYY-MM-DD") from exc
    slide_count = _require_positive(task, "slide_count", "task")
    outline = task.get("slide_outline")
    if not isinstance(outline, list) or len(outline) != slide_count:
        raise ConfigError("`task.slide_outline` 数量必须等于 `task.slide_count`")
    minimum = _require_positive(task, "product_count_min", "task")
    maximum = _require_positive(task, "product_count_max", "task")
    if minimum > maximum:
        raise ConfigError("`task.product_count_min` 不能大于 product_count_max")

    model = _require_mapping(data, "model")
    _resolve_src_path(src_dir, model.get("env_file"), "model.env_file")
    profiles = model.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ConfigError("配置字段 `model.profiles` 必须是非空 mapping")
    active_profile = str(model.get("active_profile", "")).strip()
    if active_profile not in profiles:
        raise ConfigError("`model.active_profile` 必须对应 `model.profiles` 中的一个 profile")
    for profile_name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ConfigError(f"配置字段 `model.profiles.{profile_name}` 必须是 mapping")
        for field in ("name", "api_key_env", "base_url_env"):
            if not str(profile.get(field, "")).strip():
                raise ConfigError(f"`model.profiles.{profile_name}.{field}` 不能为空")
        if profile.get("api_mode") != "responses":
            raise ConfigError(f"`model.profiles.{profile_name}.api_mode` 当前必须是 responses")
        if not isinstance(profile.get("supports_tool_calling"), bool):
            raise ConfigError(
                f"`model.profiles.{profile_name}.supports_tool_calling` 必须是 boolean"
            )
        if not isinstance(profile.get("replay_previous_output", False), bool):
            raise ConfigError(
                f"`model.profiles.{profile_name}.replay_previous_output` 必须是 boolean"
            )
        replay_mode = profile.get("tool_call_replay")
        if replay_mode is not None and replay_mode not in ("none", "function_call", "full"):
            raise ConfigError(
                f"`model.profiles.{profile_name}.tool_call_replay` 必须是 none/function_call/full"
            )
        reasoning_effort = profile.get("reasoning_effort")
        if reasoning_effort is not None and reasoning_effort not in ("low", "medium", "high"):
            raise ConfigError(
                f"`model.profiles.{profile_name}.reasoning_effort` 必须是 low/medium/high"
            )
    _require_positive(model, "max_retries", "model")
    if not isinstance(model.get("use_streaming"), bool):
        raise ConfigError("`model.use_streaming` 必须是 boolean")

    research = _require_mapping(data, "research")
    if research.get("search_provider") != "tavily":
        raise ConfigError("当前实现只支持 `research.search_provider: tavily`")

    presentation = _require_mapping(data, "presentation")
    for section_name, field in (("run", "output_dir"), ("presentation", "template")):
        raw_value = data[section_name].get(field)
        if raw_value is None:
            continue
        candidate = (src_dir / str(raw_value)).resolve()
        if candidate != src_dir and src_dir not in candidate.parents:
            raise ConfigError(f"`{section_name}.{field}` 必须指向 src 内部")
    output_filename = str(presentation.get("output_filename", ""))
    if not output_filename.endswith(".pptx"):
        raise ConfigError("`presentation.output_filename` 必须以 .pptx 结尾")
    if Path(output_filename).name != output_filename:
        raise ConfigError("`presentation.output_filename` 只能是文件名，不能包含目录")
    layout_mode = str(presentation.get("layout_mode", "fixed")).strip()
    if layout_mode not in {"fixed", "adaptive"}:
        raise ConfigError("`presentation.layout_mode` 必须是 fixed 或 adaptive")
    if layout_mode == "adaptive":
        layouts = presentation.get("layouts")
        if not isinstance(layouts, list) or not layouts:
            raise ConfigError("`presentation.layout_mode: adaptive` 时 `presentation.layouts` 必须是非空列表")
        unknown_layouts = [name for name in layouts if name not in KNOWN_LAYOUTS]
        if unknown_layouts:
            raise ConfigError(
                f"`presentation.layouts` 含未知版式 {unknown_layouts}；可用值：{list(KNOWN_LAYOUTS)}"
            )
    theme_name = presentation.get("theme")
    if theme_name is not None:
        themes = presentation.get("themes") or {}
        if not isinstance(themes, dict) or str(theme_name) not in themes:
            raise ConfigError(f"`presentation.theme` 必须对应 `presentation.themes` 中的一个条目")

    limits = _require_mapping(data, "limits")
    for field in (
        "max_model_calls",
        "max_tool_calls",
        "max_research_tool_calls",
        "max_agent_steps",
        "max_review_rounds",
        "max_elapsed_seconds",
    ):
        _require_positive(limits, field, "limits")


def load_config(path: Path) -> AppConfig:
    """读取 YAML 与私密 `.env`，校验后返回不可变配置包装器。首次使用：S0。"""

    try:
        import yaml
    except ImportError as exc:
        raise ConfigError("缺少 PyYAML；请执行 `pip install -r src/requirements.txt`") from exc

    config_path = path.resolve()
    if not config_path.is_file():
        raise ConfigError(f"配置文件不存在：{config_path}")
    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ConfigError("配置文件顶层必须是 mapping")
    src_dir = config_path.parent
    _validate_config(loaded, src_dir)
    env_path = _resolve_src_path(src_dir, loaded["model"]["env_file"], "model.env_file")
    if not env_path.is_file():
        raise ConfigError(f"私密配置文件不存在：{env_path}；请复制 core/.env.example 为 core/.env")
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ConfigError("缺少 python-dotenv；请执行 `pip install -r src/requirements.txt`") from exc
    load_dotenv(env_path, override=False)
    return AppConfig(data=loaded, config_path=config_path, src_dir=src_dir)


def validate_stage_environment(config: AppConfig) -> None:
    """按照当前阶段检查所需密钥，避免低阶段要求无关凭据。首次使用：S0。"""

    _, profile = config.active_model_profile()
    config.model_connection()
    if config.stage not in {"s0_api", "s1_structured"} and not profile["supports_tool_calling"]:
        raise ConfigError(f"当前模型 profile `{config.active_model_profile()[0]}` 不支持工具调用")
    if config.stage in {
        "s2_tools",
        "s3_workflow",
        "s4_agent",
        "s5_state",
        "s6_planning",
        "s7_reflection",
    }:
        config.credential("research", "search_api_key_env")
