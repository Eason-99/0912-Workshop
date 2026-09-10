# S3（固定 Workflow）执行说明

本文按执行顺序说明 S3 每一步由哪个文件的哪个函数完成。写法沿用 `s2_note.md`，但只保留影响功能和教学差异的部分；`Recorder`、日志文件等公共机制一笔带过。
内容依据当前 `src/` 代码整理。

## 0. 一句话概括

S3 复用 S2 的同一组工具，但**把「下一步做什么」从模型手里拿走，交给 Python 写死**：搜索 → 读页 → 抽取 Evidence → 口径检查 → 写 Deck → 生成 PPT，顺序和次数都由代码决定。

| | S2 | S3 |
| --- | --- | --- |
| 谁决定下一步 | 宿主决定回合，模型决定工具与参数 | Python 完全写死 |
| 工具调用者 | 模型发起 `ToolCall` | 代码用 `_host_call()` 直接调用 |
| 中间产物 | 只有候选来源 | 标准化 Evidence + 口径可比性报告 |
| 模型职责 | 选工具、给参数 | 只在固定位置做局部生成 |

关键差别：S2 是「单次工具协议」，S3 是「多步骤编排」。模型在 S3 里仍然要被调用三次，但它无法改变任何一步的顺序。

## 1. 主链路

```text
stages/s3_workflow.py: run()
  └─ stages/common.py: run_fixed_workflow()
       ①  _host_call("search_web", 排名查询)              宿主发起
       ②  generate_structured(product_selection)          模型：选 5–6 款产品
       ③  for 每款产品 × 2 个固定查询：
             _host_call("search_web")                     宿主发起
             _host_call("read_page")                      只读第一条候选
       ④  generate_structured(evidence_bundle)            模型：抽取标准化 Evidence
       ⑤  build_comparability_report()                    代码：按口径分组
       ⑥  generate_structured(deck_spec)                  模型：写五页 Deck
       ⑦  _host_call("create_ppt")                        宿主发起
```

模型调用固定 3 次，工具调用次数由产品数量决定（见第 3 节）。

## 2. 逐步时间线

### 启动

与 S2 完全相同的公共链路：`run.py : main()` 装配配置、运行目录、模型与工具注册表，然后分派到 `stages/s3_workflow.py : run()`。唯一差别是 S3 不调用 `run_tool_round()`，因此没有「教学回合」概念。

### 固定流程本体

| # | 动作 | 文件 : 函数 |
| --- | --- | --- |
| 1 | 读取截止日期，拼出固定的排名查询词 | `stages/common.py : run_fixed_workflow()` |
| 2 | 执行排名搜索，调用 ID 形如 `host_001` | `stages/common.py : _host_call()` |
| 3 | 把搜索摘要交给模型，选出 5–6 款产品 | `core/prompts.py : selection_prompt()` → `core/model.py : generate_structured()` |
| 4 | 校验产品数量、非空与唯一性 | `core/contracts.py : validate_products()` |
| 5 | 对每款产品依次发起两个固定查询（MAU、产品定位） | `stages/common.py : _host_call("search_web")` |
| 6 | 每条查询只取**第一条**候选并读正文 | `stages/common.py : _host_call("read_page")` → `tools/research.py : read_page()` |
| 7 | 读页失败不改变流程，只记录 `workflow_gap` 事件后继续 | `stages/common.py : run_fixed_workflow()` |
| 8 | 截断已读正文长度后筛出 `status=page_read` 的来源 | `stages/common.py : compact_sources()` |
| 9 | 让模型只从已读正文中抽取标准化 Evidence | `core/prompts.py : evidence_prompt()` → `core/model.py : generate_structured()` |
| 10 | 保存 `evidence.json` 与 `open_questions.json` | `core/context.py : persist_evidence()` |
| 11 | 按 `metric/geography/platform/unit` 对定量证据分组，缺字段的排除并说明原因 | `stages/common.py : build_comparability_report()` → `core/contracts.py : evidence_is_comparable()` |
| 12 | 保存 `comparability.json` | `stages/common.py : run_fixed_workflow()` |
| 13 | 把 products + evidence + comparability + sources 一起塞进 Deck Prompt | `core/prompts.py : deck_instructions()` |
| 14 | 生成并本地复检五页 DeckSpec | `core/model.py : generate_structured()` → `core/contracts.py : validate_deck()` |
| 15 | 生成 PPT（内部仍会检查来源是否已 `read_page`） | `stages/common.py : _host_call("create_ppt")` → `core/runtime.py : _create_ppt_handler()` → `tools/presentation.py : create_ppt()` |
| 16 | 返回 `{products, delivery, open_questions}` | `stages/common.py : run_fixed_workflow()` |

### 步骤数怎么算

```text
模型调用 = 3                # 选产品 / 抽 Evidence / 写 Deck
工具调用 = 2 + 4 × N        # 1 次排名搜索 + 每款产品(2 次搜索 + 2 次读页) + 1 次 create_ppt
其中搜索 = 1 + 2 × N        # 读页 = 2 × N（每条查询最多读 1 页）
                          # N = 选中的产品数（5–6）
```

一行代码对应一个动作：每条查询先 `search_web`，再从结果里取第一条 `read_page`，所以每款产品是 4 次工具调用，而不是 2 次。

实测（`src/runs/20260910T034440060168Z_china_ai_landscape`，5 款产品）：22 次工具调用 = 11 次搜索 + 10 次读页 + 1 次 `create_ppt`，与 `2 + 4 × 5 = 22` 一致。

## 3. 三个关键数据边界

这三步是 S3 真正的教学重点——它说明「搜索结果不是证据」：

```text
search_web 的结果        → status = candidate_only，只是候选
        ↓ read_page 之后
网页正文                 → status = page_read，才允许被引用
        ↓ 模型按 schema 抽取
Evidence                 → 带 metric/value/unit/period/geography/platform/quote
        ↓ build_comparability_report
可比较分组 / 被排除项     → 只有同口径的才允许进同一张图
```

`_create_ppt_handler()` 在最后又做了一次硬门控：Deck 引用的 `source_id` 必须已经是 `page_read`，只搜索过不算。

## 4. API 调用之间不继承历史

这是 S3 与 S4 最重要的实现差别：

- 三次 `generate_structured()` 都是**全新的 Responses 请求**，不传 `previous_response_id`；
- 它们之所以能协作，是因为 Python 把上一环节的结果显式组装进下一次 Prompt（例如 Deck 调用会收到 `products + evidence + comparability + sources` 的 JSON 文本）；
- 因此 S3 用的是**显式数据传递**，不是隐式对话连续性。这一点也是 S4 换成 Agent Loop 后最大的行为变化。

## 5. 产物

除与 S2 相同的运行骨架（`config.snapshot.yaml`、`events.jsonl`、`model_calls*`、`result.json`）外：

```text
sources.json           # 搜索到的候选 + 已读来源
evidence.json          # 标准化 Evidence（S3 独有的核心产物）
open_questions.json    # Evidence 抽取阶段留下的数据缺口
comparability.json     # 口径分组与被排除项
deck_v1.json / deck_v1.pptx / <output_filename>.pptx
```

S3 仍**不生成** `state.json`、`plan.json`、`review_*.json`（分别属于 S5、S6、S7）。

## 6. 当前局限

- **路径固定**：查到口径冲突或缺数据时不会补搜，只会记录缺口；
- **读页很浅**：每条查询只读第一条候选，不判断该结果是否真的包含所需指标；
- **模型仍可能编造**：`validate_products()` 只检查数量与唯一性，不验证产品是否真的出现在搜索结果里（靠 Prompt 约束）；
- **口径检查只做字段比对**：`evidence_is_comparable()` 只比较四个字符串字段，无法判断统计方法是否一致；
- **这就是 S4 的动机**：当下一步需要依赖刚看到的信息时，固定流程无法应对。
