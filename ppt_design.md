# Workshop PPT 设计稿：从一次 API 调用到完整 Agent

## PPT 设计约束

1. 使用 16:9 widescreen。
2. 所有元素尽可能使用 PowerPoint 原生可编辑对象。
3. 不允许整页截图或整页位图化。
4. 每页生成后必须进行视觉渲染检查，修复 overflow、overlap 和 clipping。
5. 统一使用全局 theme，不允许每页自行随机选择颜色、字号和字体。
6. 页面保持学术会议风格：高留白、低颜色数量、清晰视觉层级。
7. 不要为了填满页面增加无意义 icon、装饰性渐变、阴影或彩色卡片。
8. 一张 slide 只表达一个核心 message。
9. 图优先于文字，能通过结构图表达的信息不要写成长段文字。
10. 最终同时保留生成脚本和 `.pptx`，方便后续迭代。
11. 每一页的标题要有连贯性，除了开头结尾，其他的标题基本上要带某个stage的前缀，比如 s1 XXX，s5 xxx，你自己设计一下
## 全局叙事约束

### 讲解目标

- 受众：商科 PhD；默认了解大模型，但不要求具备 Agent 工程经验。
- 统一任务：调研中国大陆消费端通用 AI 助手市场，并生成五页中文 PPT。
- 阶段定义严格遵循 `plan.md`：S0 API、S1 Structured Output、S2 Tools、S3 Workflow、S4 Agent Loop、S5 State、S6 Planning、S7 Reflection。
- 每个 Stage 必须回答四个问题：新增了什么、此时能输出什么、仍缺少什么、为什么进入下一阶段。
- 讲解重点不是“最终做出了 PPT”，而是控制权、数据流和可观察产物怎样逐步变化。
- 核心判断：下一步动作由代码提前规定，还是由模型依据 Observation 动态选择？

### 22 页叙事结构

| 部分 | 页码 | 页面职责 | 建议时间 |
| --- | --- | --- | ---: |
| 任务与读图方式 | 1–4 | 建立统一任务、Stage 定义和增量框图规则 | 7 分钟 |
| S0 | 5–6 | 普通 API 与自由文本局限 | 4 分钟 |
| S1 | 7–8 | 结构化输出与“数据不会执行” | 4 分钟 |
| S2 | 9–10 | Tool Calling 与受限教学回合 | 5 分钟 |
| S3 | 11–12 | 固定 Workflow 与路径不可变 | 5 分钟 |
| S4 | 13–14 | Agent Loop 与 Observation 驱动动作 | 5.5 分钟 |
| S5 | 15–16 | 显式 State 与上下文管理 | 4 分钟 |
| S6 | 17–18 | Planning 与 Re-planning | 4.5 分钟 |
| S7 | 19–20 | Reflection、修订和复查 | 4.5 分钟 |
| 汇总 | 21–22 | 完整架构与控制权结论 | 1.5 分钟 |
| **合计** | **22 页** |  | **约 45 分钟** |

### 每个 Stage 的固定双页结构

- 第 A 页：`Sx · 新增机制`。以累计系统结构框图为主体，只高亮本阶段新增模块；继承模块保持低饱和度但仍可见。
- 第 B 页：`Sx · 此时能做什么，还缺什么`。左侧展示真实或示意产物，右侧固定为“当前输出 → 仍缺什么 → 下一步加入”，自然引出下一 Stage。
- S0–S7 的 A 页必须复用同一组空间锚点，听众能够通过位置不变感受系统逐步增长。
- 每个 A 页右下角必须有“本阶段新增源码”列表；只列 2–4 个最关键模块或函数，不做文件名墙。
- 每个 B 页底部必须有一个简短、明确的转场句式：`缺少 ______ → Sx：______`；S7 改为本次 Workshop 的范围边界。

### 页面字段约定

每页固定包含以下四个字段，后续生成脚本不得从备注中猜测投屏内容：

1. `标题`：页面唯一标题。
2. `文字内容`：只包含真正进入 PPT 的文字。
3. `图表内容`：说明生成方式、布局、数据流和素材来源。
4. `备注说明（不进入 PPT）`：时间、核心 message、口述、源码映射和转场。

图表生成方式只使用以下标签：

- `代码生成｜PowerPoint 原生对象`：结构框、箭头、文本框、表格和图表均保持可编辑。
- `代码生成｜项目产物转图片`：只允许日志、JSON 或 PPT 页面局部截图，不得作为整页背景。
- `用户提供｜项目运行素材`：来自 S0–S7 真实运行目录，不需要外部找图。
- `用户自行找图`：需要寻找外部图片；本套设计不依赖此类素材。
- `无`：该页不需要图表。

## 累计系统结构框图规范

### 固定空间锚点

所有 Stage 的结构框图都使用以下六列，位置不得逐页漂移：

```text
① Task / Config
      ↓
② Stage Controller → ③ Model / Contract → ④ Runtime / Tools → ⑤ State / Plan / Review → ⑥ Artifacts
                              ↑                    │                         │
                              └──── Observation ───┴─────────────────────────┘
```

- ① 输入列：`src/config.yaml`、`task_prompt()`。
- ② 控制列：`src/run.py` 和当前 `src/stages/sx_*.py`。
- ③ 模型与契约列：`core/model.py`、`core/contracts.py`。
- ④ 执行列：`core/runtime.py`、`tools/research.py`、`tools/presentation.py`。
- ⑤ 任务管理与反馈列：`TaskState`、`PlanState`、`tools/review.py`。
- ⑥ 产物列：`draft.md`、`deck.json`、`.pptx`、`state.json`、`plan.json`、`review_vN.json`。

### 增量高亮规则

- 当前 Stage 新增模块：使用饱和色、`+ NEW` 标签和 2 pt 描边。
- 已有模块：保留原位置，使用浅色填充和 1 pt 描边；不能消失，否则听众无法感知“在原系统上增加了什么”。
- 尚未出现的模块：不画实体框；仅在页脚 Stage 进度条中显示为浅灰。
- 被替换的控制方式不得直接删除：例如 S4 同时画出浅灰的 Fixed Workflow 和高亮的 Agent Loop，并用“控制权迁移”箭头说明替换关系。
- 模型用深蓝圆角矩形；契约用绿色文件卡；Runtime 用灰蓝矩形；Tool 用橙色六边形；Artifact 用绿色文件卡；Issue 用红色文件卡。
- 箭头标签只使用 `Input`、`Prompt`、`Structured Output`、`ToolCall`、`ToolResult / Observation`、`Persist`、`Patch` 七种术语。
- Recorder 作为贯穿模块固定放在结构图底部：从 S0 起一直存在，但不参与业务判断。

### 源码映射总表

| Stage | 本阶段新增或改变的关键源码 | 课堂上展示的新增机制 |
| --- | --- | --- |
| S0 | `stages/s0_api.py`、`core/model.py: generate_text()`、`core/recorder.py` | 一次文本调用与运行记录 |
| S1 | `stages/s1_structured.py`、`contracts.py: deck_schema()/validate_deck()`、`model.py: generate_structured()` | 结构化输出契约 |
| S2 | `stages/s2_tools.py`、`runtime.py: run_tool_round()/execute_call()`、`tools/research.py`、`tools/presentation.py` | ToolCall → Runtime → ToolResult |
| S3 | `stages/s3_workflow.py`、`stages/common.py: run_fixed_workflow()`、`evidence_is_comparable()` | 代码预先编排的完整流程 |
| S4 | `stages/s4_agent.py`、`stages/common.py: run_research_agent()`、`runtime.py: run_agent_loop()` | Observation 驱动下一 Action |
| S5 | `stages/s5_state.py`、`contracts.py: TaskState`、`context.py: persist_state()`、`runtime.py: _record_tool_result()` | Runtime 维护可信显式状态 |
| S6 | `stages/s6_planning.py`、`contracts.py: PlanState/plan_schema()`、`runtime.py: _update_plan_handler()` | 初始计划与有依据的 Re-plan |
| S7 | `stages/s7_reflection.py`、`presentation.py: render_ppt()/patch_deck()`、`review.py: check_deck()` | 外部检查进入修订与复查循环 |

## 全局视觉与生成规范

- 画布：`13.333 × 7.5 in`；安全边距左右 `0.65 in`、顶部 `0.45 in`、底部 `0.35 in`。
- 字体：中文“思源黑体”或“Noto Sans CJK SC”，英文与数字“Aptos”；标题 30–34 pt，正文 18–22 pt，源码标签 11–13 pt，代码 14–16 pt。
- 主色：模型/控制深蓝 `#17324D`；工具橙 `#D97706`；数据与产物绿 `#2F855A`；问题红 `#C2413B`；中性色 `#64748B`、`#E2E8F0`、白色。
- 除封面外，顶部放 S0–S7 进度条；当前 Stage 深蓝、已完成 Stage 中灰、未到 Stage 浅灰。
- 每页正文不超过 6 个要点；详细解释全部进入备注。
- 页面生成后必须渲染检查越界、重叠、裁切、字体替换和字号过小。
- 若缺少真实素材，使用带运行产物文件名的原生占位框，不得用无关图片代替。
- 备注不写入 PPT 画布；另存为 `PPT/speaker_notes.md`。
- 生成脚本、PPTX、预览和检查报告均保存在 `PPT/`。

---

## 主讲页面

## 第 1 页｜slide_id: cover

### 1. 标题

从一次 API 调用到完整 Agent

### 2. 文字内容

> 同一个任务，八次增量：S0 → S7

> 每一步都回答：加了什么？能输出什么？还缺什么？

底部关键词：

> API · Structured Output · Tools · Workflow · Agent Loop · State · Planning · Reflection

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 构图：中央只画一条尚未展开的六列系统骨架，从 `Task` 指向 `Artifacts`；S0–S7 八个小节点沿底部排列，逐渐变深。
- 封面不展示完整模块名称，避免提前泄露所有结构。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：1 分钟。
- 核心 message：这不是八个互不相关的 Demo，而是同一套系统连续增加八种能力。
- 口述：请听众始终观察三个对象：模型输出、下一步控制者、可检查产物。最终 PPT 只是载体，真正主题是系统怎样逐步成为 Agent。
- 转场：先固定整个 Workshop 使用的同一个任务。

## 第 2 页｜slide_id: task

### 1. 标题

统一任务：完成一份真实市场调研 PPT

### 2. 文字内容

> 截至指定日期，制作 5 页中文 PPT，分析中国大陆消费端通用 AI 助手的竞争格局及最近 12 个月变化。

- 选择 5–6 款独立移动 App
- 用户规模优先使用 MAU
- 趋势至少包含 3 个可比时间点
- 每个关键数字可追溯到来源

> MAU ≠ DAU ≠ 下载量 ≠ 访问量

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 构图：左侧任务输入卡；右侧五页输出缩略线框，分别为范围与结论、最新格局、12 个月变化、产品优劣势、趋势与局限。
- 中间箭头写“Research → Verify → Build”。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：任务真正困难之处是研究、核对和修订，而不是生成五页文字。
- 口述：真实来源会混用 MAU、DAU、下载量和全球访问量。一个能写 PPT 的模型不一定能发现这些口径冲突，更不一定会改变后续动作。
- 源码映射：`src/config.yaml: task`；`src/core/prompts.py: task_prompt()`。
- 转场：需要一组可观察标准判断系统究竟处于哪个阶段。

## 第 3 页｜slide_id: stage_contract

### 1. 标题

八个 Stage 按“新增控制机制”划分

### 2. 文字内容

| Stage | 新增机制 | 主要产物 |
| --- | --- | --- |
| S0 | API | `draft.md` |
| S1 | Structured Output | `deck.json` |
| S2 | Tools | Tool 轨迹、示例 PPT |
| S3 | Workflow | 完整固定流程 PPT |
| S4 | Agent Loop | 动态行动轨迹 |
| S5 | State | `state.json` |
| S6 | Planning | `plan.json` |
| S7 | Reflection | 修改前后 PPT、Review |

> 后一阶段复用前一阶段，只增加一个主要机制

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 构图：把表格转成八级横向阶梯；每一级显示 Stage、新增机制和产物，不展示实现细节。
- 颜色只分三类：控制机制深蓝、外部工具橙、状态与产物绿。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：Stage 按新增机制划分，不按“是否生成 PPT”划分。
- 口述：S1 明确停在 JSON；S2 才第一次真正创建 PPT。S3 与 S4 复用同一组工具，真正变化的是控制权。
- 转场：下一页先说明后续八张结构图应该怎样阅读。

## 第 4 页｜slide_id: diagram_legend

### 1. 标题

同一张结构图，逐个 Stage 增量加工

### 2. 文字内容

六个固定位置：

> Task → Controller → Model / Contract → Runtime / Tools → State / Plan / Review → Artifacts

视觉规则：

- `+ NEW`：本阶段新加入
- 浅色：前一阶段已有
- 实线箭头：实际数据流
- 回环箭头：Observation 改变后续动作

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 构图：展示一张带六列坐标的空结构图，并各放一个示例模块：Model、Tool、Artifact、Issue。底部固定显示 Recorder。
- 右侧放两个微型示意：S0 只有直线；S7 已形成反馈回环。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：模块位置保持不变，听众只需观察每页多出的高亮部分。
- 口述：浅色模块代表已经拥有的能力；饱和色和 `+ NEW` 代表当前新增能力。每个新增框都对应真实源码，而不是抽象装饰。
- 转场：从最小的 S0 开始，此时系统只有一条从输入到文本的直线。

## 第 5 页｜slide_id: s0_architecture

### 1. 标题

S0 · 只有一次普通 API 调用

### 2. 文字内容

> 新增机制：一次 Input → Model → Text

本阶段新增源码：

- `stages/s0_api.py: run()`
- `core/model.py: generate_text()`
- `core/recorder.py: write_text()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 累计结构框图：

```text
config.task → s0_api.run() → OpenAIModel.generate_text() → Model API → draft.md
      └──────────────────────── Recorder / events.jsonl ────────────────┘
```

- 高亮新增：`s0_api.run()`、`generate_text()`、Model API、`draft.md`。
- 尚不出现：Contracts、Runtime、Tools、State、Plan、Review。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：S0 是一次封闭请求，不具备工具或循环。
- 口述：`run.py` 读取配置并进入 `s0_api.py`；模型只返回一次自由文本；Recorder 保存请求、响应和草稿。此时宿主程序只决定“调用一次”。
- 源码映射：`src/run.py`、`src/stages/s0_api.py`、`src/core/model.py`、`src/core/recorder.py`。
- 转场：先看这条直线能够交付什么，以及它为什么不能直接进入下一段程序。

## 第 6 页｜slide_id: s0_output_gap

### 1. 标题

S0 · 能写草稿，但程序无法可靠使用

### 2. 文字内容

当前输出：

> `draft.md` · 原始请求与响应 · `events.jsonl`

仍缺什么：

- 页数、标题和来源位置可能漂移
- 没有稳定字段可交给 PPT 构建器
- 没有真实搜索，数据可能陈旧或混用口径

底部转场：

> 因为仍缺少机器可读的输出契约，S1 加入 Structured Output。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜PowerPoint 原生对象`。
- 左侧：`draft.md` 真实局部截图；标出页数漂移、来源缺失或格式不稳定的位置。
- 右侧：三段纵向链路“当前输出 → 缺口 → S1 新增 DeckSpec”，使用绿色、红色、深蓝三色。
- 素材占位：`PPT/assets/s0_draft_excerpt.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：S0 的问题不是文字质量一定差，而是自由文本不能成为稳定的软件接口。
- 口述：人可以阅读并解释草稿，但程序不能可靠定位标题、五页内容和来源。下一阶段只解决结构，不提前引入工具。
- 转场：S1 保留一次模型调用，但把自由文本换成严格 DeckSpec。

## 第 7 页｜slide_id: s1_architecture

### 1. 标题

S1 · 在模型输出后加入 DeckSpec 契约

### 2. 文字内容

> 新增机制：Structured Output + 本地校验

本阶段新增源码：

- `stages/s1_structured.py: run()`
- `contracts.py: deck_schema()/validate_deck()`
- `model.py: generate_structured()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 复用 S0 的固定位置，在 Model 与 Artifact 之间新增绿色 Contract 节点：

```text
config.task → s1_structured.run() → Model.generate_structured()
                                      ↓ Structured Output
                             DeckSpec Schema → validate_deck() → deck.json
```

- S0 的自由文本路径以浅灰保留；S1 新增的 Schema、Validate 和 `deck.json` 使用高亮绿色。
- 在 `deck.json` 右侧画断开的虚线，明确它尚未连接 PPT 工具。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：S1 改变的是模型输出契约，不是执行能力。
- 口述：Schema 规定恰好五页、稳定 ID、标题、要点、来源和 speaker notes；本地 `validate_deck()` 再检查一次。此时宿主仍只调用模型一次。
- 源码映射：`src/stages/s1_structured.py`、`src/core/contracts.py`、`src/core/model.py`。
- 转场：结构已经稳定，但外部世界仍没有发生任何动作。

## 第 8 页｜slide_id: s1_output_gap

### 1. 标题

S1 · 能输出合法 JSON，但还不能生成 PPT

### 2. 文字内容

当前输出：

> 通过校验的五页 `deck.json`

仍缺什么：

- JSON 不会自行创建文件
- 模型无法直接访问网络或运行 Python
- 运行目录中不应出现 `.pptx`

底部转场：

> 因为仍缺少影响外部环境的能力，S2 加入 Tools 与 Tool Calling。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜PowerPoint 原生对象`。
- 左侧：真实 `deck.json` 局部，突出 `id/title/bullets/source_ids`。
- 中间：`deck.json` 与 `.pptx` 之间的断裂箭头，标注“data ≠ action”。
- 右侧：即将加入的 `Runtime + create_ppt` 以深蓝虚线轮廓预告。
- 素材占位：`PPT/assets/s1_deck_json.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：Structured Output 解决机器可读性，但没有执行任何外部动作。
- 口述：S1 的关键验收条件恰恰是“没有 PPTX”。真正创建文件需要一个受 Runtime 管理的外部工具。
- 转场：S2 首次加入 Runtime、Tool Schema、ToolCall 与 ToolResult。

## 第 9 页｜slide_id: s2_architecture

### 1. 标题

S2 · 加入 Runtime 和可调用工具

### 2. 文字内容

> 新增机制：Tool Schema → ToolCall → Execute → ToolResult

本阶段新增源码：

- `stages/s2_tools.py: run()`
- `runtime.py: run_tool_round()/execute_call()`
- `tools/research.py: search_web()`
- `tools/presentation.py: create_ppt()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 复用 S1 结构，新增 Runtime 和两个橙色 Tool 节点：

```text
Model ──ToolCall──> Runtime.execute_call()
                         ├── search_web()
                         └── create_ppt()
Tool ──ToolResult / call_id──> Runtime ──> Model
```

- `DeckSpec → create_ppt() → deck_v1.pptx` 形成第一条真正的文件执行路径。
- 高亮新增：Runtime、Tool Schema、ToolCall、ToolResult、`search_web`、`create_ppt`。
- Recorder 继续在底部记录完整调用 ID 链路。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：模型只提出调用请求；Runtime 校验并执行；Tool 返回真实结果。
- 口述：模型不会直接运行 Python 或访问网络。相同 `call_id` 把一次 ToolCall 和对应 ToolResult 连接起来。S2 只做两个边界明确的教学回合。
- 源码映射：`src/core/runtime.py`、`src/stages/s2_tools.py`、`src/tools/research.py`、`src/tools/presentation.py`。
- 转场：工具已经能执行动作，但两个回合何时开始和结束仍由宿主写死。

## 第 10 页｜slide_id: s2_output_gap

### 1. 标题

S2 · 能搜索、能创建 PPT，但还不能独立完成任务

### 2. 文字内容

当前输出：

> ToolCall / ToolResult 轨迹 · `sources.json` · 示例 `deck_v1.pptx`

仍缺什么：

- 宿主规定“先搜索一次，再制作为一次”
- 搜索摘要只是候选来源，尚未 `read_page`
- 没有完整调研、证据整理和口径检查顺序

底部转场：

> 因为仍缺少端到端执行顺序，S3 加入固定 Workflow。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜项目产物转图片`。
- 左侧：从 `events.jsonl` 提取 `tool_call → tool_result → model_response` 三张局部卡片。
- 右侧：两个互不相连的回合 A/B；外部大括号标注“Host controls start / stop”。
- 素材占位：`PPT/assets/s2_events.png`、`PPT/assets/s2_deck_preview.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：拥有工具和 Tool Calling 协议仍不等于拥有自主 Agent Loop。
- 口述：`search_web` 只返回 candidate-only 来源；S2 没有读页，所以示例 PPT 不应声称研究完成。下一阶段先用最确定的方式把所有步骤串起来。
- 转场：S3 不增加新工具，而是由 Python 固定多步骤执行顺序。

## 第 11 页｜slide_id: s3_architecture

### 1. 标题

S3 · 用固定 Workflow 编排完整任务

### 2. 文字内容

> 新增机制：下一步由 Python 预先决定

本阶段新增源码：

- `stages/s3_workflow.py: run()`
- `stages/common.py: run_fixed_workflow()`
- `tools/research.py: read_page()`
- `contracts.py: evidence_is_comparable()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 复用 S2 的 Runtime 与 Tools；在 Controller 列高亮 `run_fixed_workflow()`，并用一条编号传送带连接：

```text
1 搜索排名 → 2 选择产品 → 3 搜索数据 → 4 read_page
→ 5 提取 Evidence → 6 检查口径 → 7 DeckSpec → 8 create_ppt
```

- 新增绿色数据节点：`Source`、`Evidence`、`Comparability Report`。
- 所有步骤只允许单向实线箭头，不画回环或临时分支。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：S3 已能完整交付任务，但路径控制权属于代码。
- 口述：模型仍参与产品选择、证据抽取和写作；搜索轮数、读页顺序和何时创建 PPT 都由 `run_fixed_workflow()` 决定。
- 源码映射：`src/stages/s3_workflow.py`、`src/stages/common.py`、`src/tools/research.py`、`src/core/contracts.py`。
- 转场：这条固定传送带可以交付完整 PPT，但遇到意外不会临时换路。

## 第 12 页｜slide_id: s3_output_gap

### 1. 标题

S3 · 能稳定交付完整 PPT，但路线无法适应新信息

### 2. 文字内容

当前输出：

> `sources.json` · `evidence.json` · `comparability.json` · 完整五页 PPT

仍缺什么：

- 第一条来源打不开时，只记录缺口
- 发现口径冲突后，不会自主改变查询
- 所有异常处理都依赖预设 Python 分支

底部转场：

> 因为仍缺少基于 Observation 的动态决策，S4 加入 Agent Loop。

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象` + `用户提供｜项目运行素材`。
- 左侧：固定铁轨从 Research 直达 PPT；中途放一个红色“口径冲突”障碍，列车仍只能沿原轨道前进。
- 右侧：真实 `sources/evidence/comparability` 三张文件卡和 PPT 缩略图。
- 素材占位：`PPT/assets/s3_artifacts.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：Workflow 不是低级方案；它的边界是无法处理未预设的路径变化。
- 口述：路径稳定时，S3 往往比 Agent 更可靠、更便宜。只有当下一步必须依赖刚获得的信息时，才有理由让模型拥有更多控制权。
- 转场：S4 保留同一组工具，只替换“谁决定下一步”。

## 第 13 页｜slide_id: s4_architecture

### 1. 标题

S4 · 把固定控制流替换为 Agent Loop

### 2. 文字内容

> 新增机制：Action → ToolResult / Observation → Next Action

本阶段新增源码：

- `stages/s4_agent.py: run()`
- `stages/common.py: run_research_agent()`
- `runtime.py: run_agent_loop()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- S2/S3 的 Model、Runtime 和 Tools 保持原位；Controller 列同时显示：
  - 浅灰 `run_fixed_workflow()`；
  - 高亮 `run_agent_loop()`，带 `+ NEW`。
- 画出第一次真正的回环：

```text
Model chooses Action → Runtime executes Tool → ToolResult / Observation
        ↑                                              │
        └──────────────── Next Action ─────────────────┘
```

- 循环外画四个停止出口：`completed`、`incomplete`、`limit_reached`、`error`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：S3 到 S4 的核心变化是下一步控制权从 Python 顺序迁移到模型。
- 口述：工具本身没有改变。Runtime 仍负责校验、执行、记录和停止条件；模型在每个 Observation 之后重新选择动作或 Finish。
- 源码映射：`src/stages/s4_agent.py`、`src/stages/common.py: run_research_agent()`、`src/core/runtime.py: run_agent_loop()`。
- 转场：判断这个循环是否真实存在，要看前一条 Observation 是否改变了后一条 Action。

## 第 14 页｜slide_id: s4_output_gap

### 1. 标题

S4 · 能动态补搜，但任务进度仍藏在消息历史里

### 2. 文字内容

当前输出：

> 动态 `events.jsonl` · 自主检索轨迹 · 完整 PPT · 明确结束状态

可观察轨迹：

> 搜索市场份额 → 发现口径混杂 → 改搜中国大陆移动 App MAU → 缩小范围或保留缺口

仍缺什么：

- 长消息历史重复且持续增长
- 已选产品、证据缺口和当前产物没有稳定字段
- 模型声称“完成”不等于系统真的交付

底部转场：

> 因为仍缺少可检查的任务事实，S5 加入显式 State。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜项目产物转图片`。
- 左侧：Action/Observation 交替时间线，突出第二次查询由第一次结果触发。
- 右侧：不断增长的消息堆叠，三个红色问号对应 selected products、open questions、current deck。
- 素材占位：`PPT/assets/s4_trace.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：3 分钟。
- 核心 message：Agent 的证据是外部可观察轨迹，不是隐藏思维链，也不是“用了模型”这一事实。
- 口述：如果第二次查询在第一次搜索前就写在 Python 中，它仍是 Workflow。S4 已具备动态路线，但执行事实仍主要散落在消息和事件中。
- 转场：S5 不改变 Tool 选择方式，只把真实进度整理成结构化状态。

## 第 15 页｜slide_id: s5_architecture

### 1. 标题

S5 · 在 Agent Loop 旁加入可信 TaskState

### 2. 文字内容

> 新增机制：Runtime 根据真实结果更新显式 State

本阶段新增源码：

- `stages/s5_state.py: run()`
- `contracts.py: TaskState`
- `context.py: persist_state()`
- `runtime.py: _record_tool_result()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 完整保留 S4 循环；在 ⑤ 任务管理列新增绿色 `TaskState`：

```text
ToolResult → Runtime._record_tool_result() → TaskState → state.json
                                               │
                                               └── latest state → Model prompt
```

- `TaskState` 内只展示六个字段：`metric_scope`、`source_ids`、`open_questions`、`completed_actions`、`current_deck`、`termination_reason`。
- 从 Model 到 State 不画直接写入箭头；强调模型不能自行宣告未执行的动作已完成。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：State 由 Runtime 根据执行事实维护，而不是由模型口头声明。
- 口述：`current_deck` 只有在 `create_ppt` 成功后才更新。每轮只把必要状态注入 Prompt，原始消息和事件仍保留供追溯。
- 源码映射：`src/stages/s5_state.py`、`src/core/contracts.py: TaskState`、`src/core/context.py`、`src/core/runtime.py`。
- 转场：State 解决“发生了什么”，但还没有明确表示“接下来准备做什么”。

## 第 16 页｜slide_id: s5_output_gap

### 1. 标题

S5 · 能保存可信进度，但还没有可调整的未来计划

### 2. 文字内容

当前输出：

> S4 全部产物 + 持续更新的 `state.json`

State 能回答：

- 已经完成了哪些真实动作？
- 当前有哪些来源与证据缺口？
- 是否已经成功生成当前 Deck？

仍缺什么：

- 没有步骤依赖和完成条件
- 新证据出现后，没有显式计划版本变化

底部转场：

> 因为仍缺少可观察、可修订的未来路径，S6 加入 Planning。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜PowerPoint 原生对象`。
- 左侧：`state.json` revision 前后两张局部卡，字段值由真实运行结果生成。
- 右侧：State 指向一个空的“Next?”虚线框，表现它记录过去与现在，但没有未来步骤。
- 素材占位：`PPT/assets/s5_state_before.png`、`PPT/assets/s5_state_after.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：State 与 Plan 不是同一个对象；前者描述事实，后者描述未来动作。
- 口述：短任务可以没有显式计划，但当来源口径变化需要改变多步路线时，计划版本能让变化变得可解释和可审计。
- 转场：S6 在循环开始前创建 Plan，并允许依据 Observation 更新它。

## 第 17 页｜slide_id: s6_architecture

### 1. 标题

S6 · 在 State 之上加入 Planning 与 Re-planning

### 2. 文字内容

> 新增机制：Plan → Execute → Observation → update_plan

本阶段新增源码：

- `stages/s6_planning.py: run()`
- `contracts.py: PlanState/plan_schema()`
- `stages/common.py: create_initial_plan()`
- `runtime.py: _update_plan_handler()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 保留 S5 的 Agent Loop 与 TaskState；在同一任务管理列新增 `PlanState`，位于 TaskState 上方：

```text
Goal + State → create_initial_plan() → Plan revision 1
Observation → Model ToolCall(update_plan) → Runtime validate → Plan revision 2
Plan + State ───────────────────────────────────────────────→ next Model turn
```

- `PlanState` 只显示：`objective`、`depends_on`、`status`、`required_evidence`、`revision`、`change_reason`。
- 高亮从 Observation 到 `update_plan` 的路径；旧计划进入 history，不被覆盖消失。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：Planning 的价值不在于先列步骤，而在于新证据能够改变后续执行路径。
- 口述：模型提出计划变更，Runtime 检查引用的步骤和证据后再落盘。只有执行路径变化才算 Re-plan，措辞变化不算。
- 源码映射：`src/stages/s6_planning.py`、`src/stages/common.py: create_initial_plan()`、`src/core/contracts.py: PlanState`、`src/core/runtime.py: _update_plan_handler()`。
- 转场：下一页用一次口径变化展示计划如何真正改变。

## 第 18 页｜slide_id: s6_output_gap

### 1. 标题

S6 · 能根据证据改计划，但尚未检查最终产物质量

### 2. 文字内容

当前输出：

> 初始 `plan.json` · revision history · 有依据的 change reason · 完整 PPT

计划变化：

> 单一来源覆盖 12 个月 → 发现统计范围改变 → 寻找同口径来源 → 仍缺失则拆图并标注缺口

仍缺什么：

- PPT 是否越界、过密或裁切尚未反馈给 Agent
- 数字来源、份额标签和页面结构需要外部检查
- “已经修改”尚未通过再次检查验证

底部转场：

> 因为仍缺少产物级反馈闭环，S7 加入 Reflection。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜项目产物转图片`。
- 主图：`plan revision 1 → Observation → revision 2` 的 Before/After 差异图；改变的步骤使用橙色高亮。
- 右下角放初版 PPT 缩略图，外侧三个红色问号：layout? source? label?
- 素材占位：`PPT/assets/s6_plan_v1.png`、`PPT/assets/s6_plan_v2.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：计划闭环处理执行路径，但没有自动保证最终 PPT 的内容与版面质量。
- 口述：S6 已经能够解释为什么换来源、缩小范围或保留缺口；接下来需要把 PPT 本身变成环境反馈的一部分。
- 转场：S7 在初版 PPT 后增加渲染、检查、Patch 和复查。

## 第 19 页｜slide_id: s7_architecture

### 1. 标题

S7 · 把最终 PPT 接回反馈循环

### 2. 文字内容

> 新增机制：Generate → Render → Check → Patch → Generate Again

本阶段新增源码：

- `stages/s7_reflection.py: _review_current_version()`
- `presentation.py: render_ppt()/patch_deck()`
- `review.py: check_deck()/check_ppt_bounds()`
- `contracts.py: apply_deck_patches()`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 在 S6 完整结构右侧新增红色 Review 分支，并把 Artifact 接回 Agent Loop：

```text
create_ppt → deck_v1.pptx → render_ppt → check_deck → ReviewIssue[]
      ↑                                                    │
      └──── patch_deck ← Model chooses revision action ────┘
                           ↓
                 deck_v2.pptx → render + check again
```

- 确定性检查与模型判断必须在图中分层：规则检查为实线，视觉语义判断为虚线并标注“model judgment”。
- 循环外明确标注 `max_review_rounds`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2.5 分钟。
- 核心 message：Reflection 不是让模型写一段自我评价，而是把可执行的外部 Issue 送回循环。
- 口述：检查先发现明确问题；模型根据 Issue 选择补搜或 Patch；修改后重新生成、渲染和检查。旧版本继续保留。
- 源码映射：`src/stages/s7_reflection.py`、`src/tools/presentation.py`、`src/tools/review.py`、`src/core/contracts.py: apply_deck_patches()`。
- 转场：完整闭环的证据不是一份检查报告，而是修改前后产物和复查结果。

## 第 20 页｜slide_id: s7_output_gap

### 1. 标题

S7 · 反馈已经改变产物，并被再次验证

### 2. 文字内容

当前输出：

> `deck_v1.pptx` · `review_v1.json` · `deck_patch_1.json` · `deck_v2.pptx` · `review_v2.json`

可观察闭环：

> issue_1 → DeckPatch(s2) → 页面发生变化 → issue_1 在复查中消失

本 Workshop 到此完成：

- 有研究、执行、状态、计划和产物反馈
- 每次关键变化都可追溯到事件与文件
- 无法解决的问题可以保留并明确说明

仍缺什么（超出本 Workshop）：

- 生产级重试、权限与故障恢复
- 跨任务长期记忆与系统化评测
- Multi-Agent 协作与框架迁移

底部转场：

> S7 已完成本次 Agent 闭环；再往后进入生产化与规模化问题。

### 3. 图表内容

- 生成方式：`用户提供｜项目运行素材` + `代码生成｜项目产物转图片`。
- 左右并排同一页 PPT 的 before/after 局部；中间依次放 `ReviewIssue`、`DeckPatch` 和绿色复查结果。
- 下方放五个产物文件卡，形成版本链；不能只放文字“已修复”。
- 素材占位：`PPT/assets/s7_before.png`、`PPT/assets/s7_after.png`、`PPT/assets/s7_patch.png`。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：2 分钟。
- 核心 message：反馈只有改变产物并通过复查才算闭环。
- 口述：如果没有可靠来源，正确 Patch 可能是删除数字并说明缺口，而不是制造引用。单次轨迹只能证明机制存在，不能证明平均质量一定提高。
- 转场：把 S0–S7 叠在一起，就能看到完整 Agent 是如何逐层长出来的。

## 第 21 页｜slide_id: cumulative_architecture

### 1. 标题

完整系统：S0 的直线如何长成 S7 的闭环

### 2. 文字内容

> S0 API + S1 Contract + S2 Tools + S3 Workflow + S4 Loop + S5 State + S6 Plan + S7 Review

底部产物链：

> `draft.md → deck.json → tool events → evidence → agent trace → state.json → plan.json → deck_v2 + review_v2`

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 主体是最终完整六列结构框图；所有模块恢复正常饱和度，不再使用 `+ NEW`。
- 在每个模块左上角放首次出现的 Stage 小标签，例如 Runtime 为 S2、Agent Loop 为 S4、TaskState 为 S5。
- 图下方增加一条 S0–S7 时间轴；点击感知不依赖动画，静态页面也能读懂。
- 结构图必须明确三条闭环：Tool Observation、State/Plan 回注、Review/Patch 回注。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：1 分钟。
- 核心 message：完整 Agent 不是一个新类或单一框架，而是多个清晰职责围绕控制循环协作。
- 口述：每一层都保留前面能力；模型不直接执行、Runtime 不修改事实、Tool 不决定下一步、Recorder 不参与业务判断。
- 转场：最后用“控制权、输出、缺口”三个维度回看八个阶段。

## 第 22 页｜slide_id: takeaway_matrix

### 1. 标题

判断 Agent，看控制权与反馈链

### 2. 文字内容

| Stage | 谁决定下一步 | 可观察输出 | 关键缺口 |
| --- | --- | --- | --- |
| S0–S1 | 宿主程序 | 文本 / JSON | 无外部执行 |
| S2 | 宿主控制回合 | Tool 轨迹 / 示例 PPT | 无端到端流程 |
| S3 | 固定 Python | 完整 PPT | 路径不能动态改变 |
| S4 | 模型依据 Observation | Agent 轨迹 | 无显式任务事实 |
| S5–S6 | 模型 + Runtime 校验 | State / Plan / PPT | 无产物级反馈 |
| S7 | 模型依据 ReviewIssue | 修订版本与复查 | Workshop 范围完成 |

底部结论：

> 判断 Agent，不看它做了多少事；看环境反馈是否改变了下一步

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 使用六行对比矩阵，不再重复完整结构图。
- 从 S3 到 S4 的“控制权迁移”单元格使用深蓝描边；S7 的“反馈改变产物”使用绿色描边。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 时间：0.5 分钟。
- 核心 message：真正的 Agent 式特征是 Observation 改变 Action，且改变能够由外部轨迹验证。
- 口述：实际系统不应追求最大自治。确定性规则留给代码，开放式选择交给模型；是否值得使用 Agent 取决于路径是否需要根据新信息动态变化。
- 结束方式：停在底部结论，进入提问或打开某个 Stage 的真实运行目录。

---

## 备用页面

备用页不计入 45 分钟，用于听众追问源码、契约或评价细节。

## 备用 A｜slide_id: appendix_source_map

### 1. 标题

结构框中的模块如何对应源码目录

### 2. 文字内容

```text
src/
  run.py              统一入口与 Stage 分派
  stages/             S0–S7 的控制方式
  core/model.py       模型响应适配
  core/contracts.py   共享数据契约
  core/runtime.py     Tool 分派与 Agent Loop
  tools/              Research / PPT / Review
  core/context.py     State / Plan / 产物容器
  core/recorder.py    事件与文件记录
```

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 左侧目录树，右侧完整系统框图；用同色连线逐项对应。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 核心 message：结构图不是概念拼贴，每个框都能落到一个明确源码职责。
- 口述：Stage 只负责控制流；Tool 只完成一次动作；Runtime 是唯一分派与循环实现；Contract 是跨阶段共享接口。

## 备用 B｜slide_id: appendix_contracts

### 1. 标题

核心数据契约怎样串起系统

### 2. 文字内容

> ToolCall → ToolResult
> Source → Evidence
> DeckSpec → PPT
> TaskState + PlanState → Model Context
> ReviewIssue → DeckPatch

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 五组可编辑文件卡，箭头上标负责转换的 Runtime 或 Tool。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 核心 message：Schema 保证格式和边界，来源与确定性检查约束可信度。
- 口述：结构化数据并不自动等于真实数据；Evidence 可比性仍必须检查 metric、period、geography 和 platform。

## 备用 C｜slide_id: appendix_artifacts

### 1. 标题

一次运行目录如何支持复现与课堂演示

### 2. 文字内容

```text
runs/<run_id>/
  config.snapshot.yaml
  events.jsonl
  model_calls.jsonl
  sources.json / evidence.json
  state.json / plan.json
  deck_v1.pptx / deck_v2.pptx
  review_v1.json / review_v2.json
```

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 用运行目录树连接到三类课堂素材：结构框图证据、Action/Observation 时间线、Before/After 页面。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 核心 message：演示不依赖隐藏推理，而依赖可回放的请求、工具事件、状态和版本文件。
- 口述：每次运行创建独立目录，禁止静默覆盖旧结果，保证录屏和对比能够复现。

## 备用 D｜slide_id: appendix_limits

### 1. 标题

Agent Loop 必须由 Runtime 设置边界

### 2. 文字内容

- `max_model_calls`
- `max_tool_calls`
- `max_agent_steps`
- `max_elapsed_seconds`
- `max_review_rounds`

结束状态：

> completed · incomplete · limit_reached · error

### 3. 图表内容

- 生成方式：`代码生成｜PowerPoint 原生对象`。
- 中央画 Agent Loop，外侧用五段限制器形成边界；右侧列出四种结束状态。
- 外部找图：不需要。

### 4. 备注说明（不进入 PPT）

- 核心 message：模型不能自行宣布成功，也不能无限循环。
- 口述：Runtime 必须检查 PPT 是否实际存在，并在任一预算达到上限时产生明确结束原因。

---

## 后续编码所需素材

| 素材路径 | 来源 Stage | 用于页面 | 必须展示的证据 |
| --- | --- | --- | --- |
| `PPT/assets/s0_draft_excerpt.png` | S0 | 6 | 自由文本格式或来源问题 |
| `PPT/assets/s1_deck_json.png` | S1 | 8 | 稳定字段与五页 ID |
| `PPT/assets/s2_events.png` | S2 | 10 | 同一 call_id 的请求与结果 |
| `PPT/assets/s2_deck_preview.png` | S2 | 10 | 示例 PPT，但不声称完整调研 |
| `PPT/assets/s3_workflow_artifacts.png` | S3 | 12 | Source、Evidence、Comparability、PPT |
| `PPT/assets/s4_trace.png` | S4 | 14 | Observation 改变后续 Action |
| `PPT/assets/s5_state_before.png` | S5 | 16 | 初始状态字段 |
| `PPT/assets/s5_state_after.png` | S5 | 16 | Runtime 更新后的字段 |
| `PPT/assets/s6_plan_v1.png` | S6 | 18 | 初始计划 |
| `PPT/assets/s6_plan_v2.png` | S6 | 18 | 有 change reason 的计划修订 |
| `PPT/assets/s7_before.png` | S7 | 20 | 修订前问题 |
| `PPT/assets/s7_after.png` | S7 | 20 | 可见的修订结果 |
| `PPT/assets/s7_patch.png` | S7 | 20 | slide_id、issue_ids 与修改原因 |

### 录屏建议

- S2：30–40 秒，展示 ToolCall → ToolResult 协议。
- S4：40–60 秒，展示 Observation 触发新的搜索动作。
- S7：40–60 秒，展示检查、修订和复查。
- 只展示显式动作、输入参数、结果和状态，不展示或声称还原隐藏思维链。

### 生成产物约定

- 生成脚本：`PPT/generate_workshop_ppt.py`。
- 最终演示文稿：`PPT/agent_from_scratch_workshop.pptx`。
- 讲者备注：`PPT/speaker_notes.md`。
- 逐页预览：`PPT/previews/slide_XX.png`。
- 自动检查报告：`PPT/qa_report.json`。
- 当前 `PPT/` 中上一版脚本与 PPT 不再代表本设计；下一轮编码必须按本文件重新实现。
