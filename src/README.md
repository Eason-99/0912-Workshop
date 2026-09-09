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
