# S3–S7 阶段差异与数据流补充说明

本文是 [`plan.md`](plan.md) 的补充阅读材料，依据当前 `src/` 中的实际代码说明 S3–S7 的差异。重点不是重复每个阶段“能做什么”，而是回答以下问题：

- 控制权在谁手里，谁决定下一步；
- 相比上一阶段，哪个模块的输入或输出发生了变化；
- 新增了哪些模块、数据对象和持久化文件；
- 上下游之间实际传递什么数据；
- Loop、State、Plan、Reflection 分别解决什么问题；
- 多次 API 调用之间是否包含之前的对话记录。

> 阅读时最重要的结论：S3–S7 不是简单地把前一阶段的所有中间数据逐层累加。S3 是一条由 Python 控制、显式生产 Evidence 的固定流水线；S4 改成由模型控制的工具循环。S5–S7 则在 S4 的循环上依次增加 State、Plan 和外部检查反馈。

## 1. 一张表看懂 S3–S7

| Stage | 核心变化 | 谁决定下一步 | 相比上一阶段新增的输入 | 新增的输出/持久化数据 | API 会话方式 | 是否有独立质量检查 |
| --- | --- | --- | --- | --- | --- | --- |
| S3 Workflow | 用代码写死完整调研顺序 | Python Workflow | 搜索结果、已读网页逐步组装进新的 Prompt | `sources.json`、`evidence.json`、`comparability.json`、Deck/PPT | 各次结构化生成彼此独立，代码显式传递上下文 | 有字段校验、来源校验和口径分组，但没有成品反馈循环 |
| S4 Agent Loop | 模型根据 Observation 自主选择下一工具 | 模型；runtime 限制工具和步数 | 上一轮 ToolResult，通过 Responses 会话链回传 | Agent 轨迹、来源、Deck/PPT、`AgentOutcome` | 同一个 Agent Loop 内用 `previous_response_id` 连续对话 | 没有评判成品好坏的 Reviewer |
| S5 State | 在 Agent Loop 外增加可信、显式状态 | 模型选动作；runtime 更新 State | 每轮 instructions 增加最新 `TaskState` | `state.json` | 对话链仍保留；State 是额外输入，不替代历史 | 与 S4 相同，没有新增 Reviewer |
| S6 Planning | 在 State 外增加可修改的显式计划 | 模型执行并可提议改计划；runtime 落盘 | 每轮 instructions 再增加最新 `PlanState`；工具列表增加 `update_plan` | `plan.json` 及 revision/history | 初始计划调用与 Agent Loop 是两条独立链；Loop 内连续 | 没有计划质量评分，主要靠 Schema 和日志约束 |
| S7 Reflection | 初版交付后增加“检查—修订—复查” | 检查器发现问题；模型决定如何修订 | 当前 Deck + `ReviewIssue[]` | `render_vN.json`、`review_vN.json`、`deck_patch_N.json`、新版 PPT | 每个修订回合新开会话；回合内两次调用相连 | 有确定性规则检查；没有多模态语义评分 |

用增量关系表示如下：

```text
S3  固定 Workflow
    Python 决定：search → read → Evidence → Deck → PPT

S4  Agent Loop
    模型决定：Action → Observation → 下一 Action → Finish
      │
S5  ├─ + TaskState（runtime 维护的可信执行摘要）
      │
S6  ├─ + PlanState + update_plan（显式计划及修订记录）
      │
S7  └─ + render/check + ReviewIssue + patch_deck（交付后的反馈闭环）
```

这里要特别注意：S4 复用了 S3 的工具，但没有复用 S3 的 `Evidence → comparability → Deck` 固定数据管道。S4–S7 主要依靠 Agent 会话中的 Observation 来组织研究过程。

## 2. 先区分五种容易混淆的数据

### 2.1 对话历史

对话历史是模型在当前 Responses API 会话链中能看到的先前模型输出、ToolCall 和 ToolResult。当前代码用 `previous_response_id` 让服务端把前后调用串起来。

它适合让模型理解刚才做了什么，但它不是本地可直接修改的业务对象，也不等于磁盘日志。

### 2.2 Observation / ToolResult

`ToolResult` 定义在 `src/core/contracts.py`，主要字段为：

```text
call_id + name + success + data/error
```

runtime 用 `call_id` 把它回传给对应的 ToolCall。它是下一轮决策的直接观察，例如搜索结果、网页正文、PPT 文件路径或工具错误。

ToolResult 只说明“工具返回了什么”，不天然等于“内容已经被质量评估为正确”。例如，`search_web` 的摘要仍只是候选信息；只有 `read_page` 后，该来源才会被标记为 `page_read`。

### 2.3 ExecutionContext

`ExecutionContext` 定义在 `src/core/context.py`，是一次本地运行共享的内存容器，保存：

```text
run_dir、sources、evidence、deck、state、plan、deck_version、tool_call_count
```

它给 Python 模块共享数据，并负责把部分字段落盘。它本身不会自动完整发送给模型；只有被 Prompt 函数显式序列化的部分才会成为 API 输入。

### 2.4 State

`TaskState` 是 S5 新增的结构化执行摘要，由 runtime 根据实际工具结果更新。它强调“发生过并可验证的事实”，而不是把整段聊天复制一遍。

State 的作用是：

- 让关键状态不只存在于模型会话里；
- 每轮可以显式注入，降低模型只依赖隐式上下文的风险；
- 写成 `state.json`，便于人检查和程序恢复/扩展。

State 不是对话历史的替代品。当前 S5、S6、S7 的 Agent Loop 同时使用 `previous_response_id` 和最新 State。

### 2.5 Plan

`PlanState` 是 S6 新增的“未来行动结构”，包括步骤、依赖、状态、所需证据、版本和变更原因。State 回答“现在已经发生了什么”，Plan 回答“接下来准备怎样做”。

## 3. S3：固定 Workflow

### 3.1 相比 S2 改了什么

S2 只演示一个有边界的工具调用回合；S3 首次把搜索、读页、证据抽取、口径检查、Deck 写作和 PPT 生成串成完整任务。

新增的核心编排函数是：

- 阶段入口：`src/stages/s3_workflow.py: run()`；
- 固定编排：`src/stages/common.py: run_fixed_workflow()`；
- 宿主工具调用：`src/stages/common.py: _host_call()`；
- 来源压缩：`src/stages/common.py: compact_sources()`；
- 口径分组：`src/stages/common.py: build_comparability_report()`。

### 3.2 谁是上下游

```text
config.task
  ↓
s3_workflow.run
  ↓
run_fixed_workflow
  ├─→ ToolRegistry/execute_call → search_web/read_page
  ├─→ OpenAIModel.generate_structured → 产品列表、Evidence、DeckSpec
  ├─→ ExecutionContext/Recorder → 来源、证据和比较报告
  └─→ create_ppt → deck_vN.pptx 和稳定文件名 PPT
```

上游是 `run.py` 创建的 Config、Model、ToolRegistry 和 ExecutionContext；下游是模型结构化输出、工具执行器、Recorder 和 PPT 构建器。

### 3.3 模块输入/输出怎样变化

| 模块/函数 | 主要输入 | 主要输出或副作用 | 传给谁 |
| --- | --- | --- | --- |
| `_host_call("search_web")` | 代码写定的查询词 | 候选 `Source[]`，同时更新 `context.sources` | 产品选择 Prompt，或下一次读页 |
| `generate_structured(product_selection_schema)` | 任务规则 + 排名搜索结果 | `products`、`selection_reason` | 固定的逐产品搜索循环 |
| `_host_call("read_page")` | URL + source_id | 网页正文、标题、状态等 | `context.sources`，之后进入 Evidence Prompt |
| `generate_structured(evidence_bundle_schema)` | 任务规则 + 已读来源正文 | `Evidence[]` + `open_questions[]` | Context、口径检查、Deck Prompt |
| `build_comparability_report()` | `Evidence[]` | 可比较分组 + 被排除项 | Deck Prompt、`comparability.json` |
| `generate_structured(deck_schema)` | 任务 + 产品 + Evidence + 比较报告 + 来源 | `DeckSpec` | `create_ppt` |
| `_host_call("create_ppt")` | `DeckSpec` | PPT 路径、版本化 Deck JSON | 最终交付和 Recorder |

S3 的特点是中间数据边界很清楚：搜索结果不是 Evidence；读过的网页经过模型抽取后才形成标准化 Evidence；Evidence 经口径分组后再进入 Deck 写作。

### 3.4 S3 的 API 调用是否继承历史

不继承。S3 的产品选择、Evidence 抽取、Deck 生成分别调用 `generate_structured()`，每次都是一个新的 Responses 请求，没有传 `previous_response_id`。

它们之所以仍能协作，是因为 Python 把上一环节的必要结果显式组装进下一次 Prompt。例如 Deck 调用会收到 `products + evidence + comparability + sources` 的 JSON 文本。换句话说，S3 使用的是“显式数据传递”，不是“隐式对话连续性”。

## 4. S4：Agent Loop

### 4.1 相比 S3 改了什么

S4 最大的变化是控制权转移：不再由 Python 写死每一种搜索及其顺序，而由模型根据工具返回结果决定下一次 Action。

主要入口和新增逻辑是：

- 阶段入口：`src/stages/s4_agent.py: run()`；
- Agent 适配：`src/stages/common.py: run_research_agent()`；
- 循环执行：`src/core/runtime.py: run_agent_loop()`；
- 动态指令：`src/core/prompts.py: agent_instructions()`；
- 结束结果：`src/core/runtime.py: AgentOutcome`。

`run_research_agent()` 给模型开放三个工具：

```text
search_web、read_page、create_ppt
```

### 4.2 输入/输出变化

S3 中，`run_fixed_workflow()` 的输入是整个运行依赖，输出包含 `products`、`delivery` 和 `open_questions`。S4 改成：

```text
run_agent_loop(
  prompt=完整任务,
  instructions_factory=每轮生成指令,
  allowed_names=允许的工具列表
)
→ AgentOutcome(status, steps, final_text, deck_path, error)
```

每一轮的数据链是：

```text
任务 Prompt / 上轮 previous_response_id + ToolResult
  ↓
模型返回 ToolCall[] 或普通文本
  ↓
runtime 校验工具白名单和参数 Schema
  ↓
工具执行，得到 ToolResult[]
  ↓
ToolResult 变成 function_call_output
  ↓
通过 previous_response_id 回到同一会话链
```

与 S3 相比，S4 不再单独调用产品选择 Schema、Evidence Schema 和 `build_comparability_report()`。模型直接在会话中吸收搜索/读页 Observation，最后把完整 `DeckSpec` 作为 `create_ppt` 的参数发给 runtime。

这意味着 S4 的控制更灵活，但标准化 Evidence 和口径报告不再是必经的显式中间产物。runtime 仍会做两个重要门控：

- `DeckSpec` 必须通过结构校验；
- PPT 引用的 source_id 必须已经经过 `read_page`。

### 4.3 S4 没有模型评判好坏，为什么还要多次 Loop

因为 Loop 的首要目的不是“评分”，而是完成有前后依赖的多步行动。

一次 API 调用只能先决定当前动作。例如模型想读取网页，必须先搜索得到 URL 和 source_id；网页正文要等 runtime 真正执行 `read_page` 后，下一轮模型才能看到。典型时序是：

```text
API #1：模型请求 search_web
  → runtime 返回搜索结果
API #2：模型根据结果请求 read_page
  → runtime 返回网页正文
API #3：模型发现口径不一致，再次 search_web
  → runtime 返回另一组候选来源
API #4：模型请求 read_page
  → runtime 返回可用正文
API #5：模型携带完整 DeckSpec 请求 create_ppt
  → runtime 返回 PPT 路径
API #6：模型不再调用工具，返回完成说明
```

所以，S4 的多轮是“行动—观察—再行动”，不是“生成—打分—重写”。它能让模型因 Observation 改变搜索词、继续补资料或保留缺口，但当前阶段没有独立 Reviewer 判断最终 PPT 是否足够好。

S4 的质量约束主要来自任务指令、工具参数 Schema、来源必须已读的门控、最大步数和最大调用次数。这些能阻止部分错误，但不能代替成品质量评估。真正的“检查结果驱动修订”到 S7 才出现。

### 4.4 S4 如何停止

`run_agent_loop()` 在以下情况停止：

- 模型不再返回 ToolCall：若已经生成 Deck，则为 `completed`；否则为 `incomplete`；
- 达到 `max_agent_steps` 或 `max_elapsed_seconds`：`limit_reached`；
- 请求或执行发生异常：`error`。

当前代码在 `create_ppt` 成功后还会把该 ToolResult 回传给模型一次，让模型有机会正式结束；它不是由 Reviewer 判定“质量合格”后停止。

## 5. S5：给 Agent Loop 增加显式 State

### 5.1 相比 S4 新增什么

S5 保留 S4 的工具和循环，只新增以下内容：

- 数据对象：`src/core/contracts.py: TaskState`；
- 初始化：`src/stages/common.py: make_task_state()`；
- 上下文槽位：`ExecutionContext.state`；
- 持久化：`ExecutionContext.persist_state()` → `state.json`；
- 工具后更新：`src/core/runtime.py: _record_tool_result()`；
- 结束原因更新：`src/core/runtime.py: _finish_state()`；
- Prompt 输入：`agent_instructions(..., state=...)`。

### 5.2 哪个模块的输入/输出变了

| 模块 | S4 | S5 |
| --- | --- | --- |
| Stage 入口 | 直接运行 Agent | 先创建并保存 `TaskState`，再运行 Agent |
| `instructions_factory()` 输入来源 | 仅 Config | Config + `context.state` |
| 每轮 API instructions | 固定规则 | 固定规则 + 最新 State JSON |
| `_record_tool_result()` | 记录事件、更新来源/Deck | 除原行为外，再更新 State 并写 `state.json` |
| Loop 结束 | 只返回 `AgentOutcome` | 还写入 `termination_reason` |

State 的更新链是：

```text
ToolResult
  ↓
_record_tool_result
  ├─ 成功：current_step、completed_actions、source_ids 等变化
  ├─ 失败：open_questions 增加失败信息
  └─ persist_state → state.json
  ↓
下一轮 instructions_factory 读取最新 context.state
  ↓
State JSON 再发送给模型
```

### 5.3 State 能做什么，当前还不能做什么

State 使执行事实可见、可审计，不必只依赖模型“记得”。但当前实现是精简 Demo：

- `source_ids` 会随搜索和读页结果更新；
- `completed_actions` 记录成功的工具名；
- `current_deck` 在 PPT 创建后更新；
- `open_questions` 当前主要记录工具失败，不会自动从网页内容推断研究缺口；
- `selected_products` 当前没有专门的 runtime 更新逻辑；
- State 不保存完整网页正文、完整 Evidence 或完整对话。

因此，当前 `state.json` 是执行摘要，不是完整的研究数据库。

## 6. S6：在 State 上增加 Planning 与 Re-planning

### 6.1 相比 S5 新增什么

S6 保留 S5 的 State 和 Agent Loop，增加：

- 数据对象：`src/core/contracts.py: PlanState`；
- 初始计划 Schema：`plan_schema()`；
- 初始计划 Prompt：`src/core/prompts.py: planning_prompt()`；
- 初始计划生成：`src/stages/common.py: create_initial_plan()`；
- 新工具：`update_plan`；
- 工具处理：`src/core/runtime.py: _update_plan_handler()`；
- 上下文槽位和持久化：`ExecutionContext.plan`、`persist_plan()` → `plan.json`。

### 6.2 上下游及传递数据

S6 分为两段：

```text
第一段：独立生成初始计划
config.task
  → planning_prompt
  → generate_structured(plan_schema)
  → PlanState(revision=1)
  → context.plan + plan.json

第二段：带 State 和 Plan 的 Agent Loop
TaskState + PlanState
  → agent_instructions
  → 模型选择 search/read/create_ppt/update_plan
  → ToolResult
  → runtime 更新 State 或 Plan
  → 下一轮重新注入最新 State + Plan
```

`update_plan` 传递的数据是：

```text
items[]：新的完整计划步骤列表
reason：为什么修改
```

处理后 `PlanState.replace()` 会把旧计划放进 `history`，提升 `revision`，保存新的 `change_reason` 和 `items`。下游的下一轮 Prompt 会看到最新版计划。

### 6.3 Plan 与固定 Workflow 的区别

S3 的 Workflow 是 Python 控制流，模型不能改变它；S6 的 Plan 是提供给模型参考和修改的结构化任务数据。真正执行哪个工具仍由 Agent 每轮选择。

```text
固定 Workflow：代码就是执行路线
PlanState：路线的显式描述；执行时仍要经过 Agent Loop 和工具
```

当前实现对计划更新的校验比较有限：runtime 会用严格 Tool Schema 检查字段、类型和枚举，并保存 revision/history/reason，但不会验证“修改理由是否真的被某条 Observation 支持”，也不会自动验证所有 `depends_on` 引用都存在。这些是可继续扩展的生产级能力，不应把当前 Demo 描述成已经实现。

## 7. S7：增加外部检查与 Reflection

### 7.1 相比 S6 新增什么

S7 先执行与 S6 等价的“State + 初始 Plan + Agent Loop”，获得初版 PPT，再增加成品检查和修订：

- 渲染：`src/tools/presentation.py: render_ppt()`；
- 确定性检查：`src/tools/review.py: check_deck()`；
- 评审编排：`src/stages/s7_reflection.py: _review_current_version()`；
- 修订 Prompt：`src/core/prompts.py: reflection_prompt()`；
- 修订工具：`patch_deck`；
- 修订处理：`src/core/runtime.py: _patch_deck_handler()`；
- 重建 PPT：`src/stages/s7_reflection.py: _create_revised_ppt()`。

当前代码没有单独的 `ReviewIssue` dataclass；检查结果使用字段稳定的 `dict[]` 表示，每项包含：

```text
id、slide_id、type、severity、evidence、suggestion
```

### 7.2 完整上下游

```text
S6 能力生成初版 Deck/PPT
  ↓
render_ppt → 每页图片或降级 warning → render_vN.json
  ↓
check_deck(DeckSpec, 已读 source_id, config, pptx_path)
  ↓
ReviewIssue[] → review_vN.json
  ├─ 空：结束
  └─ 非空：进入修订回合
       ↓
     reflection_prompt(当前 DeckSpec + ReviewIssue[])
       ↓
     模型调用 patch_deck，传递整页替换 Patch
       ↓
     runtime 更新 context.deck，保存 deck_patch_N.json
       ↓
     create_ppt → 新版 deck_vN.json / deck_vN.pptx
       ↓
     再次 render + check
       ↓
     无问题或达到 max_review_rounds 后结束
```

`check_deck()` 当前检查文字条数、字符数、未知来源、数字是否缺少来源、份额标签和 PPT 元素是否越界。渲染图片会保存下来，但当前没有把图片送给多模态模型做语义或审美评分。因此 S7 有外部、确定性的质量反馈，但还不是完整的视觉审稿系统。

如果本机缺少渲染依赖，`render_ppt()` 的错误会被记录成 warning，后续可执行的 Deck 和 PPT 边界检查仍会继续。

## 8. API 调用到底会不会附带之前的对话记录

答案是：**取决于调用属于哪一条会话链；State 和对话历史是两套独立机制。**

### 8.1 同一个 Agent Loop 内：会继承

S4、S5、S6，以及 S7 的“初版生成 Agent Loop”内部使用：

```text
首轮：start_tool_turn(prompt, instructions, tools)
后续：continue_tool_turn(
        previous_response_id=上一轮 response.id,
        function_outputs=本轮 ToolResult,
        instructions=最新 instructions,
        tools=同阶段工具 Schema
      )
```

因此模型不是只看到 State。通过 `previous_response_id`，服务端会话链还关联此前的模型输出、ToolCall 和 ToolResult；同时代码每轮重新传递最新 instructions 和工具 Schema。

需要注意不同服务商对这条链路的要求并不一致。DeepSeek 不会依据 `previous_response_id` 复原工具调用链：它要求下一轮请求把上一轮的 `reasoning` 与 `function_call` 输出项原样回放，否则会直接返回 400 `No tool call found for tool output with call_id ...`，即使该 `call_id` 确实来自上一条响应。因此 `profiles.*.replay_previous_output` 控制 `continue_tool_turn()` 是否在工具结果前补回上一轮输出项：DeepSeek 需要开启，标准 OpenAI-compatible 端点保持关闭。

S4 虽然没有 State，仍能依赖这条会话链理解前面的搜索和读页结果。S5/S6 则是在同一机制之外，再显式加入 State/Plan。

### 8.2 独立任务之间：不会自动继承

以下调用会新开会话，不自动携带上一条链的历史：

- S3 的每一次 `generate_structured()`；
- S6/S7 的“生成初始 Plan”与之后的 Agent Loop；
- S7 初版 Agent Loop与 Reflection 修订回合；
- S7 不同 Reflection 轮次之间。

这些调用所需的上下文必须由代码重新放进 Prompt。例如 S7 的 `reflection_prompt()` 明确放入“当前 DeckSpec + 当前 ReviewIssue[]”，所以即使不继承 S6 的完整对话，也能针对当前成品修订。

每个 `run_tool_round()` 内部的两次调用仍是相连的：第一次让模型发出 `patch_deck`，第二次用 `previous_response_id` 回传 Patch 的工具结果。但下一轮 Review 会再次调用新的 `start_tool_turn()`。

### 8.3 磁盘调用记录不会自动成为模型上下文

`model_calls.jsonl` 和 `model_calls/` 中的 request、原始 output、完整 response 文件用于审计与回放。保存到磁盘不代表下一次 API 会自动读取它们。只有以下两种数据会进入后续模型请求：

1. 通过 `previous_response_id` 连接的服务端会话内容；
2. Python 显式放入新的 `prompt`、`instructions` 或 `function_call_output` 的内容。

当前代码没有“把整段本地完整历史重新拼回请求”的通用降级实现，只针对工具调用链提供了 `replay_previous_output`：开启后会在回传 `function_call_output` 前补上上一轮的原始输出项。因此第三方 Responses API 仍需真正兼容并保存 response ID 链路；仅仅接受单次 Responses 请求还不够。

## 9. 各阶段主要落盘文件

所有运行产物位于对应的 `src/runs/<run_id>/`。模型调用记录是各阶段共有的，下面只列阶段特有或主要产物。

| Stage | 主要文件 | 含义 |
| --- | --- | --- |
| S3 | `sources.json` | 搜索和已读来源 |
| S3 | `evidence.json` | 从已读正文抽取的标准化证据 |
| S3 | `open_questions.json` | Evidence 抽取阶段留下的数据缺口 |
| S3 | `comparability.json` | 指标、地区、终端和单位口径分组 |
| S3–S7 | `deck_vN.json`、`deck_vN.pptx` | 版本化 Deck 和 PPT |
| S4–S7 | `events.jsonl` | ToolCall、ToolResult、交付等执行轨迹 |
| S5–S7 | `state.json` | 最新显式 TaskState |
| S6–S7 | `plan.json` | 最新 Plan、revision 和历史版本 |
| S7 | `render_vN.json` | 渲染结果或降级 warning |
| S7 | `review_vN.json` | 每一版的 ReviewIssue 列表 |
| S7 | `deck_patch_N.json` | 模型提出的页面修订参数 |

所有 Stage 的每轮模型请求还统一记录到：

```text
model_calls.jsonl
model_calls/model_call_XXX_request.json
model_calls/model_call_XXX_output.txt
model_calls/model_call_XXX_response.json
```

这套记录回答“实际发了什么 Prompt、模型原始返回了什么”；State/Plan 文件回答“程序当前认可的任务状态和计划是什么”。二者用途不同。

## 10. 容易误解的地方

### Loop 不等于 Reflection

- Loop：为完成多步任务，重复 Action → Observation；S4 首次出现。
- Reflection：用独立检查结果评价已有产物，再定向修改；S7 首次出现。

### State 不等于对话历史

- 对话历史通过 `previous_response_id` 维持，内容丰富但隐式依赖服务端；
- State 是 runtime 维护的精简事实，可落盘、可审计、可显式注入。

### Plan 不等于 Workflow

- Workflow 是 Python 已经写死的执行控制；
- Plan 是 Agent 可以参考和替换的数据，不能自行执行。

### ToolResult 不等于质量结论

- ToolResult 证明工具执行结果是什么；
- ReviewIssue 才表示 S7 检查器认为成品存在什么问题；
- 当前 Review 仍只覆盖有限的确定性规则，不证明内容全面、商业判断正确或视觉效果优秀。

### 后一阶段不一定保留前一阶段所有显式数据

S4–S7 没有经过 S3 的 `evidence.json + comparability.json` 必经管道。它们复用工具与来源校验，并把更多研究推理留在 Agent 会话里。这是教学上为了突出“控制权变化”的精简设计，也是当前实现的重要局限。

## 11. 建议讲解时使用的主线

如果要用一句问题串起 S3–S7，可以按以下顺序讲：

```text
S3：如果每一步都确定，代码怎样稳定完成任务？
S4：如果下一步取决于刚看到的信息，谁来选择 Action？
S5：如果不能只相信模型记忆，哪些执行事实需要显式保存？
S6：如果原路线被新证据推翻，如何表示并记录计划变化？
S7：如果生成完成不代表质量合格，谁提供外部反馈并触发修订？
```

这五个阶段分别引入的是固定编排、自主决策、显式状态、可修改计划和质量反馈，而不是五套互不相关的 PPT 生成方案。
