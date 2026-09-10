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

`continue_tool_turn()` 默认按标准 OpenAI-compatible 行为，用 `previous_response_id` + `function_call_output` 接回工具结果。DeepSeek 不依据 `previous_response_id` 复原工具调用链，会返回 400 `No tool call found for tool output with call_id ...`。因此 `model.profiles.<name>.replay_previous_output` 控制是否在工具结果前回放上一轮的原始输出项（含 `reasoning`）：`deepseek` 设为 `true`，标准 OpenAI-compatible 端点保持 `false`。新增 profile 时若遇到同类报错，把该项改为 `true` 即可。

另外，S2 的两个教学回合使用 `run_tool_round(..., close_tools=True)`，在回传工具结果的那一轮设置 `tool_choice: none`，由宿主保证“模型选择工具 → runtime 执行 → 模型总结”在固定回合内结束；S4–S7 的 Agent Loop 不设该限制，模型可以继续选择下一个动作。

## 输出截断与 `response.incomplete`

推理模型的思考 token 也计入 `model.max_output_tokens`。当一次请求接近上限时，服务端会以 `response.incomplete`（`incomplete_details.reason = max_output_tokens`）结束；而 OpenAI SDK 的 `get_final_response()` 只承认 `response.completed`，会抛出 `RuntimeError: Didn't receive a response.completed event.` 并丢掉真实原因。`OpenAIModel._stream_response()` 改为显式消费事件流并读取终止事件，因此现在会报出真实原因，同时截断前的部分输出仍会落盘。

实测 S3 抽取 Evidence 的一次调用需要约 18K 输出 token（思考占 11.7K），因此 `max_output_tokens` 设为 32000。若日后仍遇到截断，优先提高该值，或缩小单次请求要生成的内容。

## Agent Loop 的工具额度

`limits.max_tool_calls` 按**逐次工具调用**计数：模型一轮可以并行发起多个调用，额度消耗比轮数快得多。实测 S4 完成「调研 + 交付」需要 41 次调用（17 次搜索 + 23 次读页 + 1 次 `create_ppt`），因此默认额度设为 60、`max_agent_steps` 为 25、`max_model_calls` 为 40。

`agent_instructions()` 每轮会告知模型**剩余额度**，让它为交付预留一次 `create_ppt`。若额度仍被耗尽，loop 的结束原因会记为 `limit_reached`（而不是笼统的 `incomplete`），错误信息中带上 `max_tool_calls` 的实际取值。

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
