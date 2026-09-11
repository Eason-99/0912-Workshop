# Workshop Demo 使用说明

本目录包含完整的 S0–S7 Demo：代码、唯一配置文件、可选素材、测试和运行产物。该说明文件首次在 S0 使用。

## 运行方式

1. 安装依赖：`python -m pip install -r src/requirements.txt`。
2. 将 `src/core/.env.example` 复制为 `src/core/.env`，填写准备使用的模型 URL 和 Key；S2–S7 还需填写 `TAVILY_API_KEY`。
3. 在 `src/config.yaml` 中设置 `model.active_profile`（`deepseek` 或 `third_party`）并选择 `run.stage`。
4. 从仓库根目录运行 `python src/run.py`。

执行时不需要命令行参数。所有非敏感运行输入都位于 `config.yaml`；URL 与 Key 集中在 `core/.env`。真实 `.env` 已被 `.gitignore` 忽略，仓库只保留无真实凭据的 `.env.example`。

## 模型调用记录

每次运行都会创建统一的 `model_calls.jsonl`。每轮调用先写 `phase=request`；成功后追加 `phase=response`，失败则追加 `phase=error`，同一轮通过 `call_id` 关联。

```text
runs/<run_id>/
  model_calls.jsonl
  model_calls/
    model_call_001_request.json   # 最终 API payload，包含 input/instructions/tools
    model_call_001_output.txt     # 未执行 strip 的原始 response.output_text
    model_call_001_response.json  # 完整 SDK 响应；由 recording.save_messages 控制
```

S0 的 `draft.md` 直接使用同一份原始 `output_text`；`model_call_001_output.txt` 是独立留存副本。API Key 不会进入上述记录。

两种模型连接均走 OpenAI-compatible Responses API，并默认流式接收响应：

| `active_profile` | `.env` 中读取 | 用途 |
| --- | --- | --- |
| `deepseek` | `DEEPSEEK_BASE_URL`、`DEEPSEEK_API_KEY` | 支持 Responses 的 DeepSeek 服务或对应代理 |
| `third_party` | `THIRD_PARTY_BASE_URL`、`THIRD_PARTY_API_KEY` | 支持 Responses 的第三方 API |

可运行 `python src/tests/check_api_connections.py` 对两个 profile 分别发起最小真实请求。该脚本不会打印 API Key，也不会被普通单元测试自动调用。

## 工具调用链的服务商差异

标准做法是用 `previous_response_id` + `function_call_output` 接回工具结果，由服务端自己关联那条工具调用。但实测两个 profile 都不这么做：它们会接受 `previous_response_id` 却完全不解释它（传一个不存在的 UUID 也照样返回 200），于是收到 `function_call_output` 时就报 400 `No tool call found for function call output with call_id ...`。

`model.profiles.<name>.tool_call_replay` 控制这种情况下的回放策略，三档：

| 取值 | 行为 | 适用 |
| --- | --- | --- |
| `none` | 只发 `function_call_output` | 真正实现会话存储的标准端点 |
| `function_call` | 先补最小化的 `function_call` 项（仅 type/call_id/name/arguments） | 第三方 profile；回放完整输出项会被它拒绝（`Unknown parameter: 'input[0].status'`） |
| `full` | 回放上一轮完整输出项，含 `reasoning` | DeepSeek；只补 `function_call` 会报 `reasoning_text must be passed back` |

新增 profile 时若遇到同类 400，先试 `function_call`，再试 `full`。旧的布尔开关 `replay_previous_output` 仍被兼容（`true` 等价于 `full`）。

推理模型还会在每个响应里消耗大量思考 token。实测 DeepSeek 一次调用最多产生 11K 思考 token、耗时 182 秒，18 次串行调用就撞到 `max_elapsed_seconds=900`。`model.profiles.<name>.reasoning_effort` 可设为 `low` / `medium` / `high`（不设则不发送该参数），`deepseek` 默认 `low`，实测能把单次思考耗时砍掉约一半。

另外，S2 的两个教学回合使用 `run_tool_round(..., close_tools=True)`，在回传工具结果的那一轮设置 `tool_choice: none`，由宿主保证“模型选择工具 → runtime 执行 → 模型总结”在固定回合内结束；S4–S7 的 Agent Loop 不设该限制，模型可以继续选择下一个动作。

## 输出截断与 `response.incomplete`

推理模型的思考 token 也计入 `model.max_output_tokens`。当一次请求接近上限时，服务端会以 `response.incomplete`（`incomplete_details.reason = max_output_tokens`）结束；而 OpenAI SDK 的 `get_final_response()` 只承认 `response.completed`，会抛出 `RuntimeError: Didn't receive a response.completed event.` 并丢掉真实原因。`OpenAIModel._stream_response()` 改为显式消费事件流并读取终止事件，因此现在会报出真实原因，同时截断前的部分输出仍会落盘。

实测 S3 抽取 Evidence 的一次调用需要约 18K 输出 token（思考占 11.7K），因此 `max_output_tokens` 设为 32000。若日后仍遇到截断，优先提高该值，或缩小单次请求要生成的内容。

## Agent Loop 的工具额度

`limits.max_tool_calls` 按**逐次工具调用**计数：模型一轮可以并行发起多个调用，额度消耗比轮数快得多。实测 S4 完成「调研 + 交付」需要 41 次调用（17 次搜索 + 23 次读页 + 1 次 `create_ppt`），因此默认额度设为 60、`max_agent_steps` 为 25、`max_model_calls` 为 40。

`agent_instructions()` 每轮会告知模型**剩余额度**，让它为交付预留一次 `create_ppt`。若额度仍被耗尽，loop 的结束原因会记为 `limit_reached`（而不是笼统的 `incomplete`），错误信息中带上 `max_tool_calls` 的实际取值。

额度只是上限，真正拖垮长任务的是**重复劳动**。实测一次 S5 跑满 30 轮失败，其中读页 42 次里有 9 次是同一个 URL（199IT 那篇被读了 5 遍），并最终因为引用了只搜索过、没读过的来源而被 `create_ppt` 拒绝。对应的三处防护：

- `execute_call()` 按「工具名 + 规范化参数」缓存成功结果（`read_page` 按 URL 归一，忽略变化的 `source_id`）。重复调用直接返回缓存并标记 `duplicate`，不执行、不消耗额度，并写入 `tool_call_duplicate` 事件；
- `_search_handler()` 返回 `new_source_count`；为 0 时附上提示，告诉模型该方向已无新信息；
- `TaskState` 把来源拆成 `verified_source_ids`（已 `read_page`，可被 Deck 引用）与 `candidate_source_ids`（仅搜索候选），模型不必再靠猜。

光有额度上限还不够：实测两次 S5 都在 30 轮内用掉 70 多次调用却始终没有交付（一次根本没调用 `create_ppt`）。因此又加了一道**交付窗口**：`limits.max_research_tool_calls` 单独限制 `search_web` / `read_page`，用尽后 runtime 只接受 `create_ppt`，并返回“只能用已核验来源生成五页 Deck，拿不到同口径数据就写成缺口”。每轮指令同时报出当前轮次与剩余额度，并要求剩余不足三分之一时必须交付。

`create_ppt` 被拒时的报错也补上了下一步动作（先 `read_page` 核对，或移除这些来源），模型据此能自己修回来——实测一次运行里第一次 `create_ppt` 因引用未核验来源失败，模型按提示改完后第二次成功交付。

## 页面图表

`DeckSpec` 的每一页都带 `chart` 字段，`type` 取 `none` / `bar` / `line`。它不是可选字段——JSON Schema 是 strict 的，可选字段会被服务端拒绝，因此用 `type: "none"` 表达“本页无图”。

三层协作：

| 层 | 位置 | 职责 |
| --- | --- | --- |
| 契约 | `core/contracts.py: chart_schema()` / `_validate_chart()` | 约束结构，并拒绝缺分类、缺序列或 `values` 与 `categories` 不等长的图 |
| 渲染 | `tools/presentation.py: _add_chart()` | 用 python-pptx 生成**原生可编辑图表**；有图时正文缩到左半版面 |
| 要求 | `core/prompts.py: chart_rules()` | s2 必须画“样本内 MAU 份额”柱状图；s3 只有凑齐 ≥3 个同口径时间点才画折线，否则留空并声明缺口 |

Review 侧加了两条规则（`review.require_chart_for_share`）：s2/s3 既没有图也没有缺口声明时报 `chart_missing`；有图但与 `bullets` 无法对应、数值长度不一致或整页没有来源时报 `invalid_chart` / `chart_without_source`。只有 s2/s3 受“必须有图”约束——s1、s5 这类叙述页提到“份额”通常只是口径说明，不应强制配图。

## 文本框换行

`python-pptx` 的 `add_textbox()` 默认写出 `<a:bodyPr wrap="none"><a:spAutoFit/></a:bodyPr>`，含义是**不自动换行**：文字会沿单行向右溢出文本框，只有在 PowerPoint 里手动拖一下形状、触发重新排版时才会缩回来。`_add_textbox()` 因此显式设置了 `word_wrap = True`、`auto_size = MSO_AUTO_SIZE.NONE`，并把四边内边距归零（`lIns/rIns/tIns/bIns = 0`），让代码里的英寸坐标就是文本的实际起点。`tests/test_presentation.py` 会直接解包 PPTX 断言 `wrap="square"` 且不含 `spAutoFit`。

换行生效后文字会变高，所以同一处还加了确定性的自动适配：`_estimate_line_count()` 按框宽估算换行后的行数（全角字符记 1 个宽度单位、半角记 0.55），`_fit_font_size()` 从首选字号逐磅下调直到放进文本框（正文 18pt→最低 10pt，有图页 14pt 起，标题 26pt→最低 16pt）。缩过字的页面会出现在 `create_ppt()` 返回值的 `shrunk_font_pages` 里，便于确认。

这里刻意没有用 `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`（normAutofit）：它依赖 PowerPoint 打开后重新排版才写入 `fontScale`，在写入之前查看仍会溢出——和上面那个 `wrap="none"` 属于同一类“要手动碰一下才生效”的问题。字号在代码里算，结果才是可复现的。

另外三处容易踩的排版坑也一并修了：`_style_paragraph()` 会在 `latin` 之外补 `<a:ea>` / `<a:cs>`（否则中文字体不生效）；正文每条 bullet 拆成独立段落并显式设置 `line_spacing` 与 `space_after`（否则行距由主题默认值决定，和估算不一致）；正文框高度按估算行数收紧，不再留一截空白。

## 版式与主题（模式开关）

`presentation.layout_mode` 决定页面结构由谁决定：

| 模式 | 行为 |
| --- | --- |
| `fixed`（默认） | 版式固定为 `bullets`，输出与历史版本一致 |
| `adaptive` | 模型可在 `presentation.layouts` 列出的版式里自选 |

五种版式的词表定义在 `core/contracts.py: KNOWN_LAYOUTS`，渲染实现在 `tools/presentation.py: LAYOUT_RENDERERS`，`tests/test_presentation.py` 断言两者一致。

| 版式 | 渲染 | 适用 |
| --- | --- | --- |
| `bullets` | 单栏要点；有图表时正文让出右半版面 | 定性叙述 |
| `two_column` | 要点按数量对半分成左右两栏 | 并列的两组信息 |
| `comparison_table` | python-pptx 原生可编辑表格 | 多对象 × 多指标（s2、s4） |
| `chart_focus` | 图表占主体、要点压缩到下方 | 数据页（s2、s3） |
| `custom` | 按 `elements` 列表流式排版 | 模型自由组合页面元素 |

`layout` 和 `table` 都是**必需字段**（第 8 节那条 strict schema 约束使然），无表格时用空 `columns`/`rows` 表示。渲染器在缺少本版式所需数据时会回退到 `bullets`，避免出现空白页。

`custom` 版式的元素类型有 `callout`（一句话结论 + 强调色条）、`kpi`（大号数字 + 标签）、`bullets`、`chart`、`table`。每个元素带 `cols`（3/4/6/8/12，占 12 列栅格的几列）和 `emphasis`（low/medium/high），布局引擎负责把栅格换算成英寸、按顺序流式排版并在放不下时换行——模型只声明“有什么、占多宽、多强调”，不写坐标。

`presentation.theme` 是视觉主题开关，只改字体与字号、不改结构。内置 `classic`（26/18pt）与 `compact`（22/16pt）两套，各自定义 `font_family`、各级字号，以及表格用的 `accent` / `accent_text` 配色；主题缺失的键会回退到 `presentation` 顶层同名键，再回退到代码内置默认值。

## S7 的模型评审与版面溢出

S7 的检查分两层：确定性规则（`check_deck` / `check_ppt_bounds`）和可选的模型评审。`review.model_review: true` 时，每轮规则检查之后会把当前 `DeckSpec` 交给模型做一轮语义评审（`review_deck_with_model`），产出 `content_gap` / `contradiction` / `off_outline` / `clarity` / `structure` 类问题。模型问题一律 `severity=warning` 且带 `source: "model"`，不阻塞交付；规则问题带 `source: "rule"`。`review.max_model_issues` 限制每轮最多采纳条数。

自定义布局的溢出之前是检查盲区：`check_ppt_bounds` 只看 shape 是否超出画布，不知道文本有没有溢出文本框、有没有压到来源行。现在 `simulate_custom_flow()` 用和渲染器同一套几何模拟排版，`check_deck` 对 `custom` 页做 `custom_layout_overflow`（error）检查；渲染端也在超出正文区时截断并返回 `overflow_pages`。

## Stage 对照

| Stage | 模块 | 新增概念 |
| --- | --- | --- |
| S0 | `stages/s0_api.py` | 一次文本响应 |
| S1 | `stages/s1_structured.py` | 严格 DeckSpec JSON，不生成 PPT |
| S2 | `stages/s2_tools.py` | 有边界的 Tool Calling |
| S3 | `stages/s3_workflow.py` | 代码控制的固定 Workflow |
| S4 | `stages/s4_agent.py` | 模型控制的 Agent Loop |
| S5 | `stages/s5_state.py` | 显式、可验证的 State |
| S6 | `stages/s6_planning.py` | Planning 与 Re-planning |
| S7 | `stages/s7_reflection.py` | 渲染、检查、修订反馈循环 |

每个 Python 文件都有中文模块 docstring，每个手写函数都有中文作用说明和“首次使用：Sx”标记。完整模块调用关系见 `数据流说明.md`。
