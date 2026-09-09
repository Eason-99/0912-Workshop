# Workshop 讲者备注

此文件不会写入 PPT 画布。

## 1. 从一次 API 调用到完整 Agent

- slide_id：`cover`
- Stage：OPEN
- 建议时间：1 分钟
- 核心 message：同一套系统连续增加八种能力。
- 口述：持续观察模型输出、下一步控制者和可检查产物。
- 口述：最终 PPT 是载体，主题是控制循环如何形成。
- 转场：先固定整个 Workshop 使用的同一个任务。

## 2. 统一任务：完成一份真实市场调研 PPT

- slide_id：`task`
- Stage：TASK
- 建议时间：2 分钟
- 核心 message：任务难点是研究、核对和修订，而不是生成文字。
- 口述：来源会混用 MAU、DAU、下载量和访问量。
- 口述：每个阶段处理同一个任务，便于比较新增能力。
- 转场：需要一组可观察标准判断系统处于哪个阶段。

## 3. 八个 Stage 按“新增控制机制”划分

- slide_id：`stage_contract`
- Stage：MAP
- 建议时间：2 分钟
- 核心 message：后一阶段复用前一阶段，只增加一个主要机制。
- 口述：S1 只输出 JSON，S2 才创建 PPT。
- 口述：S3 与 S4 的差异是控制权，不是工具集合。
- 转场：下一页说明八张结构图应该怎样阅读。

## 4. 同一张结构图，逐个 Stage 增量加工

- slide_id：`diagram_legend`
- Stage：MAP
- 建议时间：2 分钟
- 核心 message：位置不变，只观察新增高亮与新增数据流。
- 口述：浅色是继承能力，+ NEW 是本阶段新增。
- 口述：每个结构框都对应真实源码职责。
- 转场：从 S0 开始，此时系统只有一条直线。

## 5. S0 · 只有一次普通 API 调用

- slide_id：`s0_architecture`
- Stage：S0
- 建议时间：2 分钟
- 核心 message：S0 是一次封闭请求，不具备工具或循环。
- 口述：宿主只决定调用模型一次。
- 口述：自由文本对人友好，但不是稳定的软件接口。
- 转场：下一页检查当前输出与关键缺口。

## 6. S0 · 能写草稿，但程序无法可靠使用

- slide_id：`s0_output_gap`
- Stage：S0
- 建议时间：2 分钟
- 核心 message：S0 是一次封闭请求，不具备工具或循环。
- 口述：宿主只决定调用模型一次。
- 口述：自由文本对人友好，但不是稳定的软件接口。
- 转场：因为仍缺少机器可读的输出契约，S1 加入 Structured Output。

## 7. S1 · 在模型输出后加入 DeckSpec 契约

- slide_id：`s1_architecture`
- Stage：S1
- 建议时间：2 分钟
- 核心 message：S1 改变输出契约，而不是执行能力。
- 口述：Schema 规定字段，本地 validate_deck 再检查一次。
- 口述：S1 的验收条件是没有 PPTX。
- 转场：下一页检查当前输出与关键缺口。

## 8. S1 · 能输出合法 JSON，但还不能生成 PPT

- slide_id：`s1_output_gap`
- Stage：S1
- 建议时间：2 分钟
- 核心 message：S1 改变输出契约，而不是执行能力。
- 口述：Schema 规定字段，本地 validate_deck 再检查一次。
- 口述：S1 的验收条件是没有 PPTX。
- 转场：因为仍缺少影响外部环境的能力，S2 加入 Tools 与 Tool Calling。

## 9. S2 · 加入 Runtime 和可调用工具

- slide_id：`s2_architecture`
- Stage：S2
- 建议时间：2.5 分钟
- 核心 message：模型提出请求，Runtime 校验并执行，Tool 返回真实结果。
- 口述：相同 call_id 连接一次请求与结果。
- 口述：有工具不等于已经具备 Agent Loop。
- 转场：下一页检查当前输出与关键缺口。

## 10. S2 · 能搜索、能创建 PPT，但还不能独立完成任务

- slide_id：`s2_output_gap`
- Stage：S2
- 建议时间：2 分钟
- 核心 message：模型提出请求，Runtime 校验并执行，Tool 返回真实结果。
- 口述：相同 call_id 连接一次请求与结果。
- 口述：有工具不等于已经具备 Agent Loop。
- 转场：因为仍缺少端到端执行顺序，S3 加入固定 Workflow。

## 11. S3 · 用固定 Workflow 编排完整任务

- slide_id：`s3_architecture`
- Stage：S3
- 建议时间：2.5 分钟
- 核心 message：S3 能完整交付，但整体路径由 Python 控制。
- 口述：Workflow 不是低级方案，稳定路径往往更适合它。
- 口述：此阶段新增的是固定编排，不是新工具。
- 转场：下一页检查当前输出与关键缺口。

## 12. S3 · 能完成任务，但路线无法根据结果改变

- slide_id：`s3_output_gap`
- Stage：S3
- 建议时间：2 分钟
- 核心 message：S3 能完整交付，但整体路径由 Python 控制。
- 口述：Workflow 不是低级方案，稳定路径往往更适合它。
- 口述：此阶段新增的是固定编排，不是新工具。
- 转场：因为仍缺少 Observation 驱动的动态选择，S4 加入 Agent Loop。

## 13. S4 · 把固定控制流替换为 Agent Loop

- slide_id：`s4_architecture`
- Stage：S4
- 建议时间：2.5 分钟
- 核心 message：S4 的关键变化是下一步控制权迁移到模型。
- 口述：真实证据是 Observation 改变后续 Action。
- 口述：只展示显式动作，不展示隐藏思维链。
- 转场：下一页检查当前输出与关键缺口。

## 14. S4 · 能动态补搜，但进度仍藏在消息历史里

- slide_id：`s4_output_gap`
- Stage：S4
- 建议时间：3 分钟
- 核心 message：S4 的关键变化是下一步控制权迁移到模型。
- 口述：真实证据是 Observation 改变后续 Action。
- 口述：只展示显式动作，不展示隐藏思维链。
- 转场：因为仍缺少可检查的任务事实，S5 加入显式 State。

## 15. S5 · 在 Agent Loop 旁加入可信 TaskState

- slide_id：`s5_architecture`
- Stage：S5
- 建议时间：2 分钟
- 核心 message：State 由 Runtime 根据执行事实维护。
- 口述：current_deck 只有在 create_ppt 成功后更新。
- 口述：State 描述发生了什么，不描述未来动作。
- 转场：下一页检查当前输出与关键缺口。

## 16. S5 · 能保存可信进度，但还没有未来计划

- slide_id：`s5_output_gap`
- Stage：S5
- 建议时间：2 分钟
- 核心 message：State 由 Runtime 根据执行事实维护。
- 口述：current_deck 只有在 create_ppt 成功后更新。
- 口述：State 描述发生了什么，不描述未来动作。
- 转场：因为仍缺少可观察、可修订的未来路径，S6 加入 Planning。

## 17. S6 · 在 State 之上加入 Planning 与 Re-planning

- slide_id：`s6_architecture`
- Stage：S6
- 建议时间：2.5 分钟
- 核心 message：Planning 的价值在于新证据改变执行路径。
- 口述：措辞变化不算 Re-plan，执行路径变化才算。
- 口述：旧计划进入 history，不静默覆盖。
- 转场：下一页检查当前输出与关键缺口。

## 18. S6 · 能根据证据改计划，但还没检查最终产物

- slide_id：`s6_output_gap`
- Stage：S6
- 建议时间：2 分钟
- 核心 message：Planning 的价值在于新证据改变执行路径。
- 口述：措辞变化不算 Re-plan，执行路径变化才算。
- 口述：旧计划进入 history，不静默覆盖。
- 转场：因为仍缺少产物级反馈闭环，S7 加入 Reflection。

## 19. S7 · 把最终 PPT 接回反馈循环

- slide_id：`s7_architecture`
- Stage：S7
- 建议时间：2.5 分钟
- 核心 message：反馈改变产物并通过复查，才形成完整闭环。
- 口述：Reflection 不是自我评价文字。
- 口述：无法解决时应保留缺口，不能编造来源。
- 转场：下一页检查当前输出与关键缺口。

## 20. S7 · 反馈已经改变产物，并被再次验证

- slide_id：`s7_output_gap`
- Stage：S7
- 建议时间：2 分钟
- 核心 message：反馈改变产物并通过复查，才形成完整闭环。
- 口述：Reflection 不是自我评价文字。
- 口述：无法解决时应保留缺口，不能编造来源。
- 转场：S7 已完成本次 Agent 闭环；再往后进入生产化与规模化问题。

## 21. 完整系统：S0 的直线如何长成 S7 的闭环

- slide_id：`cumulative_architecture`
- Stage：ALL
- 建议时间：1 分钟
- 核心 message：完整 Agent 是多个清晰职责围绕控制循环协作。
- 口述：模型不直接执行，Tool 不决定下一步，Recorder 不参与业务判断。
- 口述：三条闭环分别是 Observation、State/Plan 回注和 Review/Patch。
- 转场：最后用控制权与输出矩阵回看八个阶段。

## 22. 判断 Agent，看控制权与反馈链

- slide_id：`takeaway_matrix`
- Stage：END
- 建议时间：0.5 分钟
- 核心 message：环境反馈是否改变下一步，是可观察的核心判断。
- 口述：确定性规则留给代码，开放式选择交给模型。
- 口述：实际系统不应追求最大自治。
- 转场：进入提问或打开真实运行目录。

## 23. 结构框中的模块如何对应源码目录

- slide_id：`appendix_source_map`
- Stage：APP
- 建议时间：备用
- 核心 message：每个框都能落到明确的源码职责。
- 口述：Stage 负责控制流，Tool 只执行一次动作。
- 口述：Runtime 是唯一工具分派与循环实现。

## 24. 核心数据契约怎样串起系统

- slide_id：`appendix_contracts`
- Stage：APP
- 建议时间：备用
- 核心 message：Schema 约束格式，来源和检查约束可信度。
- 口述：结构化数据不自动等于真实数据。
- 口述：Evidence 可比性必须检查 metric、period、geography 和 platform。

## 25. 一次运行目录如何支持复现与课堂演示

- slide_id：`appendix_artifacts`
- Stage：APP
- 建议时间：备用
- 核心 message：可回放文件替代隐藏推理。
- 口述：每次运行创建新目录，禁止静默覆盖。
- 口述：课堂展示请求、工具事件、状态和版本文件。

## 26. Agent Loop 必须由 Runtime 设置边界

- slide_id：`appendix_limits`
- Stage：APP
- 建议时间：备用
- 核心 message：模型不能自行宣布成功，也不能无限循环。
- 口述：Runtime 检查 PPT 是否实际存在。
- 口述：达到任一预算上限都产生明确结束原因。
