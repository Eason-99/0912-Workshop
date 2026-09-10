# S2（Tool Calling）执行说明

本文按执行顺序说明 S2 每一步由哪个文件的哪个函数完成、输入输出是什么、落了什么盘。
内容依据当前 `src/` 代码与一次真实运行（`src/runs/20260910T025916255122Z_china_ai_landscape`）整理，只覆盖 S2。

## 0. 一句话概括

S2 在 S1「模型能输出结构化数据」之上，第一次引入**统一工具层**：模型提出 `ToolCall`，runtime 校验并执行，再把 `ToolResult` 回传给模型。

但 S2 **不是 Agent Loop**：走几个回合、什么时候开始和结束，由宿主代码写死；模型只决定「调用哪个工具、传什么参数」。因此它展示的是 **Tool Calling** 这一条协议，而不是自主决策。

两个教学回合：

| 回合 | 工具 | 目的 |
| --- | --- | --- |
| 回合 A | `search_web` | 展示「模型请求 → runtime 执行 → 结果回传」 |
| 回合 B | `create_ppt` | 展示结构化数据只有经过 ToolCall 才会变成真实文件 |

核心对比：S1 的 `deck.json` 只是文件里的 JSON，不会执行任何外部动作；到 S2，模型发出 `create_ppt` 调用，runtime 才真正写出 `.pptx`。

## 1. 参与文件

| 文件 | 角色 | 在 S2 中的职责 |
| --- | --- | --- |
| `src/run.py` | 入口 | 零参数启动、装配依赖、分派到 S2、写 `result.json` |
| `src/core/config.py` | 配置 | 校验配置、加载 `.env`、检查 S2 所需凭据 |
| `src/core/recorder.py` | 记录 | 创建运行目录，写 `events.jsonl` 与 `model_calls*` |
| `src/core/model.py` | 模型接口 | 发起 Responses 请求、解析 `ToolCall`、回传 `ToolResult` |
| `src/core/context.py` | 共享容器 | 保存一次运行的 `sources`、`deck`、调用计数等 |
| `src/core/runtime.py` | 工具运行时 | 工具注册、Schema 校验、执行分派、`run_tool_round()` |
| `src/core/prompts.py` | Prompt | 组装任务 Prompt 与教学回合指令 |
| `src/core/contracts.py` | 契约 | `ToolCall` / `ToolResult` / `DeckSpec` Schema 与 `validate_deck()` |
| `src/tools/research.py` | 工具实现 | `search_web()` |
| `src/tools/presentation.py` | 工具实现 | `create_ppt()` |
| `src/stages/s2_tools.py` | 阶段控制 | 决定跑哪两个回合、顺序和结束点 |

`core/runtime.py: build_tool_registry()` 会注册 5 个工具（`search_web`、`read_page`、`create_ppt`、`update_plan`、`patch_deck`），但 S2 每个回合只把其中 1 个放进白名单暴露给模型。

## 2. 执行时间线

### 阶段 0：启动与装配（第 1–11 步，尚未进入 S2 本体）

| # | 动作 | 文件 : 函数 |
| --- | --- | --- |
| 1 | 固定读取 `src/config.yaml`，不接收命令行参数 | `run.py : main()` |
| 2 | 校验 stage、日期、页数、产品数量、各限制项，并把相对路径解析到 `src/` 内 | `core/config.py : load_config()` → `_validate_config()` |
| 3 | 加载 `core/.env`，把 URL/Key 注入环境变量 | `core/config.py : load_config()` → `load_dotenv()` |
| 4 | 检查 active profile 的连接信息和工具调用能力；S2 还要检查 `TAVILY_API_KEY` | `core/config.py : validate_stage_environment()` |
| 5 | 用 UTC 时间生成不覆盖历史结果的 `run_id` | `core/recorder.py : create_run_id()` |
| 6 | 创建 `src/runs/<run_id>/`，初始化 `events.jsonl` 和 `model_calls.jsonl` | `core/recorder.py : Recorder.__init__()` |
| 7 | 保存 `config.snapshot.yaml`，并写入 `run_started` 事件 | `run.py : main()` → `Recorder.write_text()` / `Recorder.record()` |
| 8 | 依据 active profile 创建模型客户端 | `core/model.py : OpenAIModel.__init__()` |
| 9 | 创建本次运行的共享容器（此时 `sources`、`deck` 均为空） | `core/context.py : ExecutionContext` |
| 10 | 注册全部工具定义（S2 只暴露子集） | `core/runtime.py : build_tool_registry()` |
| 11 | 动态导入并调用 `stages/s2_tools.py` 的入口 | `run.py : _load_runner()` → `stages/s2_tools.py : run()` |

### 阶段 1：回合 A —— `search_web`

| # | 动作 | 文件 : 函数 |
| --- | --- | --- |
| 12 | 读取 `task.data_cutoff_date`，拼出「搜索截至 X 的中国大陆 AI 助手 App MAU 排名候选来源」这一固定查询 | `stages/s2_tools.py : run()` |
| 13 | 发起一个有边界的教学回合：`prompt` + 指令 + 只允许 `search_web`，`close_tools=True` | `core/runtime.py : run_tool_round()` |
| 14 | 把白名单工具转成 Responses API 的扁平函数 Schema | `core/runtime.py : ToolRegistry.schemas()` → `ToolDefinition.openai_schema()` |
| 15 | **模型调用 1**：开始新的工具回合（不带 `previous_response_id`） | `core/model.py : start_tool_turn()` → `_create()` |
| 16 | 发出请求前先落盘最终 payload，并追加 `model_calls.jsonl` 的 `phase=request` | `core/recorder.py : record_model_request()` |
| 17 | 流式接收响应，保存 `output.txt`（原始 `output_text`）与完整 `response.json` | `core/recorder.py : record_model_response()` |
| 18 | 从响应中解析函数调用，得到 `ToolCall(call_id, name, arguments)` 列表 | `core/model.py : extract_tool_calls()` → `_parse_tool_calls()` |
| 19 | 校验该回合确实发起了工具调用，否则报错（S2 不允许模型直接给文本） | `core/runtime.py : run_tool_round()` |
| 20 | **逐次执行工具**：检查 `max_tool_calls`、计数 +1、记录 `tool_call` 事件、检查白名单 | `core/runtime.py : execute_call()` |
| 21 | 按 Schema 递归校验模型给的参数，再分派到具体 handler | `core/runtime.py : ToolRegistry.execute()` → `_validate_schema_value()` |
| 22 | 调用 Tavily 搜索，标准化为带 `source_id`、`status=candidate_only` 的候选来源 | `core/runtime.py : _search_handler()` → `tools/research.py : search_web()` |
| 23 | 把结果写入 `context.sources` 并落盘 `sources.json` | `core/runtime.py : _search_handler()` → `core/context.py : persist_sources()` |
| 24 | 记录 `tool_result` 事件（S2 未启用 State，因此不更新 `state.json`） | `core/runtime.py : _record_tool_result()` |
| 25 | 把每个结果包成 `function_call_output`（携带同一个 `call_id`） | `core/runtime.py : tool_output_item()` |
| 26 | **模型调用 2**：带着 `previous_response_id`、上一轮输出项和工具结果回到模型；因 `close_tools=True` 同时发 `tool_choice: none`，禁止再调工具，强制给出文本总结 | `core/model.py : continue_tool_turn()` → `_create()` |
| 27 | 返回该回合的总结文本，作为 `search_summary` | `core/runtime.py : run_tool_round()` |

### 阶段 2：回合 B —— `create_ppt`

| # | 动作 | 文件 : 函数 |
| --- | --- | --- |
| 28 | 组装 PPT 回合的 Prompt：明确本阶段不做充分调研、**每页 `source_ids` 必须为空**、缺失数字改为说明缺口 | `core/prompts.py : bounded_ppt_prompt()` |
| 29 | 发起第二个教学回合，只允许 `create_ppt` | `core/runtime.py : run_tool_round()` |
| 30 | **模型调用 3**：模型输出一条 `create_ppt` 调用，参数是完整 `DeckSpec` | `core/model.py : start_tool_turn()` → `_create()` |
| 31 | 执行 `create_ppt` 调用 | `core/runtime.py : execute_call()` → `_create_ppt_handler()` |
| 32 | 先校验 DeckSpec：恰好五页、页面 ID 依次为 `s1`–`s5`、字段类型正确 | `core/contracts.py : validate_deck()` |
| 33 | 门控：PPT 引用的每个 `source_id` 必须已经 `read_page` 核对过，否则拒绝 | `core/runtime.py : _create_ppt_handler()` |
| 34 | 保存版本化 Deck：`deck_v1.json` | `core/runtime.py : _create_ppt_handler()` → `Recorder.write_json()` |
| 35 | 用 python-pptx 逐页添加标题、正文、来源和页码文本框，写出 `deck_v1.pptx` | `tools/presentation.py : create_ppt()` → `_add_textbox()` |
| 36 | 复制一份稳定文件名（`presentation.output_filename`），便于录屏时路径不变 | `core/runtime.py : _create_ppt_handler()` → `shutil.copyfile()` |
| 37 | 更新 `context.deck` 与 `deck_version`，记录 `presentation_created` 事件 | `core/runtime.py : _create_ppt_handler()` → `Recorder.record()` |
| 38 | **模型调用 4**：回传工具结果并再次以 `tool_choice: none` 收尾 | `core/model.py : continue_tool_turn()` |
| 39 | 返回 PPT 回合总结，作为 `ppt_summary` | `core/runtime.py : run_tool_round()` |

### 阶段 3：收尾

| # | 动作 | 文件 : 函数 |
| --- | --- | --- |
| 40 | 把两个回合的总结写成 `tool_round_summaries.md`，并返回 `{"search_summary", "ppt_summary"}` | `stages/s2_tools.py : run()` → `Recorder.write_text()` |
| 41 | 保存 `result.json`，写入 `run_finished: completed`，并在终端打印运行目录 | `run.py : main()` |

失败路径不需要额外代码：任一步抛异常都会回到 `run.py : main()` 的 `except` 分支，写入 `result.json` 与 `run_finished: status=error`；而**工具自身**的失败不会崩溃，而是变成 `ToolResult(success=False, error=...)` 回传给模型（见第 6 节）。

## 3. 控制权边界

```text
宿主代码（stages/s2_tools.py）
  决定：跑两个回合、每回合用哪个工具、何时结束
        │
模型（core/model.py）
  决定：工具名 + 参数
        │
Runtime（core/runtime.py）
  执行：Schema 校验、白名单、计数、调用 handler、回传结果
        │
Tools（src/tools/*）
  只完成一次外部动作，不决定后续步骤
```

三个必须区分的概念：

- **Tool** 是可调用函数（`tools/research.py`、`tools/presentation.py`）；
- **Tool Calling** 是「模型生成调用请求 → runtime 执行 → 结果回传」的协议（`core/model.py` + `core/runtime.py`）；
- **Agent Loop** 是模型根据 Observation 自主决定下一步，S2 还没有，从 S4 才出现。

## 4. 产物

```text
src/runs/<run_id>/
  config.snapshot.yaml          # 本次配置快照
  events.jsonl                  # tool_call / tool_result / presentation_created 等
  model_calls.jsonl             # 4 次调用的 request/response 索引
  model_calls/
    model_call_001_request.json # 回合 A 首次请求（含 search_web Schema）
    model_call_001_output.txt   # 原始 output_text
    model_call_001_response.json
    model_call_002_*.{json,txt} # 回合 A 带 tool_choice=none 的收尾调用
    model_call_003_*.{json,txt} # 回合 B 首次请求（含 create_ppt Schema）
    model_call_004_*.{json,txt} # 回合 B 收尾调用
  sources.json                  # 搜索到的候选来源
  deck_v1.json                  # 版本化 DeckSpec
  deck_v1.pptx                  # 版本化 PPT
  china_ai_landscape.pptx       # presentation.output_filename 指定的稳定副本
  tool_round_summaries.md       # 两个回合的模型总结
  result.json                   # 阶段返回值
```

S2 **不会**生成 `evidence.json`、`comparability.json`、`state.json`、`plan.json`、`review_*.json`，这些分别属于 S3、S5、S6、S7。

## 5. 实测轨迹

来自 `src/runs/20260910T025916255122Z_china_ai_landscape`：

```text
model_call_001  tools=[search_web]   → 2 条 function_call（同一轮并行搜索）
   ├─ tool_call  search_web  "中国大陆 AI 助手 App MAU 排名 2026"
   ├─ tool_result success=true  → sources.json
   ├─ tool_call  search_web  "AI 助手 App 月活跃用户 排行榜 中国 2026年"
   └─ tool_result success=true  → sources.json
model_call_002  previous_response_id + tool_choice=none → 文本总结（search_summary）
model_call_003  tools=[create_ppt]  → 1 条 function_call（携带完整 DeckSpec）
   └─ tool_call create_ppt → tool_result success=true → presentation_created
        deck_v1.json / deck_v1.pptx / china_ai_landscape.pptx
model_call_004  previous_response_id + tool_choice=none → 文本总结（ppt_summary）
run_finished status=completed
```

对应的 `model_call_002` 请求体顺序是：

```text
input = [ reasoning, function_call(call_00...), function_call(call_01...),
          function_call_output(call_00...), function_call_output(call_01...) ]
```

即先回放上一轮输出项，再追加工具结果。回放是 DeepSeek 的硬性要求，见下一节。

## 6. 关键约束与常见故障

**1）`No tool call found for tool output with call_id ...`（400）**

DeepSeek 的 `/responses` 不依据 `previous_response_id` 复原工具调用链，必须在下一轮请求中回放上一轮的 `reasoning` 与 `function_call` 输出项，否则报此 400——即使该 `call_id` 确实来自上一条响应。由 `model.profiles.deepseek.replay_previous_output: true` 控制，逻辑在 `core/model.py : continue_tool_turn()`；标准 OpenAI-compatible 端点保持 `false`。

**2）回合被模型拖长**

模型在收到工具结果后可能继续发起新的工具调用，而 `run_tool_round()` 只执行一轮。S2 因此传入 `close_tools=True`，在收尾那一轮发送 `tool_choice: none`，由宿主而不是模型决定回合结束。S4–S7 的 Agent Loop 不设该限制。

**3）`create_ppt` 引用未读来源**

`_create_ppt_handler()` 要求每个 `source_id` 都已经 `read_page`。S2 没有读页步骤，所以 Prompt 必须要求 `source_ids` 留空；否则模型的编造 ID 会被门控拦下，只返回一条失败 Observation。

**4）工具失败不崩溃**

`execute_call()` 把异常统一转成 `ToolResult(success=False, error=...)`。这是刻意的：失败应该成为模型可见的观察，而不是终止进程。

**5）S2 的结论为什么不能直接当结论用**

`search_web` 的摘要只是 `status=candidate_only` 的候选信息；S2 没有 `read_page`、没有标准化 Evidence、没有口径可比性检查。这些从 S3 才开始出现。
