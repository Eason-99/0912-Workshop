"""集中生成各阶段 Prompt，同时把可变任务输入留在配置中。首次使用：S0。"""

from __future__ import annotations

import json
from typing import Any

from core.config import AppConfig


def task_prompt(config: AppConfig) -> str:
    """根据配置字段拼装所有阶段共享的市场调研任务。首次使用：S0。"""

    task = config.section("task")
    outline = "\n".join(f"{index}. {title}" for index, title in enumerate(task["slide_outline"], start=1))
    scope_rule = (
        "同一图表必须使用相同指标、地区、终端范围和单位。"
        if task.get("require_same_scope_for_chart", True)
        else "允许按页面说明的口径并列展示，但不得把不同指标误称为可比趋势。"
    )
    missing_rule = (
        "无法取得同口径数据时明确保留缺口，禁止推测或补造。"
        if task.get("allow_missing_data", True)
        else "若关键数据缺失，则不要交付对应比较，并在结果中报告任务未完成。"
    )
    return f"""任务：截至 {task['data_cutoff_date']}，为{task['audience']}制作 {task['slide_count']} 页中文内容，分析{task['market']}的竞争格局及最近 {task['lookback_months']} 个月变化。

输出语言：{task['language']}。

研究范围：只纳入中国大陆普通消费者使用、以独立移动 App 为主要入口的通用 AI 助手；排除企业 API、云服务、办公软件或手机系统内置功能及主要服务海外市场的产品。根据最新可比数据选择 {task['product_count_min']}–{task['product_count_max']} 款产品，不预设名单。

指标规则：优先使用 {task['primary_metric']}。MAU、DAU、下载量、访问量和全球数据不能混入同一趋势图。份额只能称为“样本内 MAU 份额”，并说明用户可能同时使用多个 App。{scope_rule}{missing_rule}

页面结构：
{outline}
"""


def chart_rules() -> str:
    """生成各阶段共用的图表要求，供 Deck 写作和 Agent 指令复用。首次使用：S3。"""

    return """图表要求：每页都必须给出 chart 字段，没有同口径数据时用 type="none"。
- s2「最新竞争格局」必须用 type="bar" 画“样本内 MAU 份额”：categories 为产品名，series 为 [{"name": "样本内 MAU 份额", "values": [百分数数值]}]，unit 为 "%"。
- s3「最近 12 个月变化」只有凑齐 ≥3 个同口径时间点时才用 type="line" 画趋势；凑不齐就保持 type="none"，并在 bullets 中写明缺失的时间点。
- 其余页面没有同口径数据时一律 type="none"，categories 与 series 留空数组。
- chart 的数值必须来自已 read_page 核对的来源，values 与 categories 等长，不得为凑图编造数字。"""


def layout_rules(config: AppConfig) -> str:
    """生成页面版式与表格字段要求，按当前版式目录裁剪。首次使用：S3。"""

    catalog = config.layout_catalog()
    if catalog == ["bullets"]:
        return (
            "版式：本阶段 layout 固定填 \"bullets\"；"
            "table 字段的 caption/columns/rows 全部留空（空字符串与空数组），表格只在 comparison_table 版式下使用。"
        )
    return f"""版式：每页必须从 {catalog} 中选一个 layout，并按内容性质选择：
- bullets：要点列表，适合定性叙述。
- two_column：要点分左右两栏，适合并列的两组信息。
- comparison_table：多对象 × 多指标的比较，适合“最新竞争格局”“产品定位与优劣势”，必须填 table 字段。
- chart_focus：以图表为主、要点为辅，适合数据页。
- custom：用 elements 列表自由组合页面元素。
table 字段：columns 是表头，rows 每行的单元格数必须与 columns 相同；没有表格时 caption/columns/rows 全部留空。
表格里的数字同样必须来自已 read_page 核对的来源。

当 layout 为 custom 时，elements 按顺序排列元素，每个元素必须有 type、cols、emphasis 三个字段：
- type 取 callout（一句话结论）、kpi（大号数字+标签）、bullets（要点）、chart（图表）、table（表格）之一；
- cols 取 3/4/6/8/12，表示占 12 列栅格中的几列；每行各元素 cols 之和不要超过 12；
- emphasis 取 low/medium/high，表示视觉强调程度；
- callout 填 text；kpi 填 value 与 label；bullets 填 items；chart 填 chart 数据；table 填 table 数据，其余字段留空。
- 布局引擎负责实际坐标，模型只声明“有什么、占多宽、多强调”，不得编造来源数据。"""


def deck_instructions(config: AppConfig, source_context: str = "") -> str:
    """生成约束五页 `DeckSpec` 写作和来源引用的指令。首次使用：S1。"""

    task = config.section("task")
    return f"""你是严谨的商业研究演示文稿作者。输出必须符合给定 JSON Schema，恰好 {task['slide_count']} 页，页面 ID 依次为 s1–s{task['slide_count']}。每页不超过 6 个 bullet。只引用上下文中真实存在的 source_id；没有可靠数据时说明缺口，不补造数字。

{chart_rules()}

{layout_rules(config)}

来源上下文：
{source_context or '当前阶段未提供联网来源，因此不得声称已经完成实时检索。'}
"""


def tool_demo_instructions() -> str:
    """限制教学回合只做一次清晰可观察的工具调用。首次使用：S2。"""

    return "调用提供的唯一工具完成任务。不要声称自己执行了工具；等待 runtime 返回结果后再简短总结。"


def bounded_ppt_prompt(config: AppConfig) -> str:
    """生成 S2 中只演示 `create_ppt` 且不引用未核验来源的教学 Prompt。首次使用：S2。"""

    return (
        task_prompt(config)
        + "\n本阶段只演示把结构化内容交给 create_ppt，不要声称完成了充分调研。"
        + "\n本阶段没有任何经过 read_page 核验的来源，因此每页 source_ids 必须是空数组，禁止编造 source_id；"
        + "需要外部数据的数字改为说明当前缺口。"
    )


def agent_instructions(
    config: AppConfig,
    state: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
    remaining_tool_calls: int | None = None,
    step: int | None = None,
    max_steps: int | None = None,
) -> str:
    """生成 Agent Loop 指令，并按阶段加入可选 State 和 Plan。首次使用：S4。"""

    context_parts = [
        "你是调研与 PPT 制作 Agent。根据工具 Observation 决定下一步。",
        "先搜索候选来源，再 read_page 核对正文。搜索摘要不能直接当作关键数字证据。",
        "create_ppt 只能引用 State 中 verified_source_ids 里的来源；candidate_source_ids 只是搜索候选，引用会被 runtime 拒绝。",
        "若搜索结果返回 new_source_count=0，说明该方向已无新信息：立即停止这个方向，改用已读来源或把缺口写进结论，不要换几个近义词反复搜同一件事。",
        "调研额度用尽后 runtime 只接受 create_ppt。交付本身就是任务的一部分：证据够写五页就交付，不要为了追求完整而把额度耗尽。",
        "同一指标若检索若干次仍拿不到同口径数据，就按缺口处理并交付，不要为了凑时间点无限检索。",
        "只把同指标、同地区、同终端范围的数据放入同一比较。找不到时保留缺口。",
        "完成五页 DeckSpec 后必须调用 create_ppt；create_ppt 成功即表示本阶段交付完成。",
        f"最多选择 {config.section('task')['product_count_max']} 款产品。",
        chart_rules(),
        layout_rules(config),
    ]
    if state is not None:
        context_parts.append("当前可信 State：\n" + json.dumps(state, ensure_ascii=False, indent=2))
    if plan is not None:
        context_parts.append("当前 Plan：\n" + json.dumps(plan, ensure_ascii=False, indent=2))
        context_parts.append("若 Observation 推翻当前路径，可调用 update_plan，但必须写清依据。")
    if remaining_tool_calls is not None:
        # 额度是有限资源，模型必须知道还剩多少才可能为交付预留调用。
        progress = f"当前第 {step} 轮（上限 {max_steps} 轮）。" if step and max_steps else ""
        context_parts.append(
            f"{progress}剩余工具调用额度：{remaining_tool_calls}。交付五页 PPT 至少需要 1 次 create_ppt，"
            "请为它预留额度；剩余额度或剩余轮次不足三分之一时，必须停止检索、立即交付。"
        )
    return "\n\n".join(context_parts)


def selection_prompt(config: AppConfig, search_results: list[dict[str, Any]]) -> str:
    """要求模型从排名搜索结果中选择符合范围的产品。首次使用：S3。"""

    return task_prompt(config) + "\n候选搜索结果：\n" + json.dumps(search_results, ensure_ascii=False, indent=2)


def evidence_prompt(config: AppConfig, sources: list[dict[str, Any]]) -> str:
    """要求模型只抽取有来源正文支持的标准化 Evidence。首次使用：S3。"""

    return task_prompt(config) + f"""

从以下来源提取可核查 Evidence。metric/value/unit/period/geography/platform 不明确时使用空字符串，并把缺口写入 open_questions。quote 必须是来源正文中的短片段，source_id 必须原样引用。

来源：
{json.dumps(sources, ensure_ascii=False, indent=2)}
"""


def planning_prompt(config: AppConfig) -> str:
    """要求模型生成包含依赖关系的初始调研计划。首次使用：S6。"""

    return task_prompt(config) + "\n请生成精简计划，覆盖候选产品、同口径 MAU、趋势、产品定位、PPT 交付。初始 status 全部设为 pending。"


def reflection_prompt(deck: dict[str, Any], issues: list[dict[str, Any]]) -> str:
    """要求模型针对具体检查问题调用 `patch_deck`。首次使用：S7。"""

    return f"""根据检查问题修订 DeckSpec。调用 patch_deck，只替换确实需要修改的页面；保留可靠事实和来源 ID，不得为通过检查而编造来源。

当前 DeckSpec：
{json.dumps(deck, ensure_ascii=False, indent=2)}

ReviewIssue：
{json.dumps(issues, ensure_ascii=False, indent=2)}
"""


def deck_review_prompt(config: AppConfig, deck: dict[str, Any]) -> str:
    """要求模型评审 DeckSpec，只提结构与逻辑问题，不补造事实。首次使用：S7。"""

    outline = "\n".join(
        f"{index}. {title}"
        for index, title in enumerate(config.section("task")["slide_outline"], start=1)
    )
    return f"""你是严格的演示文稿评审者。只基于下面的 DeckSpec 提出需要修改的问题，不要补造事实或数字。

只关注这些问题类型：
- off_outline：页面没有回答大纲里对应一项的要求；
- contradiction：页面之间或页面内部自相矛盾；
- content_gap：本该有论证或对比的地方缺失；
- clarity：表述含糊、层级混乱、要点没有重点；
- structure：页面结构不适合当前内容。

约束：
- 证据写进 evidence（引用 DeckSpec 里的原文片段），建议写进 suggestion；
- 不得建议新增数字或“补找数据”；只能建议重组、精简、改写；
- 没把握就不写，宁缺毋滥，最多 5 条。

要求的大纲：
{outline}

当前 DeckSpec：
{json.dumps(deck, ensure_ascii=False, indent=2)}
"""
