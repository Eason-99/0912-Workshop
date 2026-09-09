"""读取唯一配置并分派当前阶段的零参数程序入口。首次使用：S0。"""

# 延迟解析类型注解，避免仅用于类型提示的对象在启动时被提前求值。
from __future__ import annotations

# 动态导入当前配置选中的 Stage 模块。
import importlib
# 将最终运行结果格式化为中文可读的 JSON。
import json
# 使用绝对路径定位 `src` 和唯一配置文件。
from pathlib import Path
# 将启动或运行错误输出到标准错误流。
import sys
# 描述 Stage 入口函数的类型签名。
from typing import Any, Callable

# 加载配置、读取配置类型，并按 Stage 校验所需环境变量。
from core.config import AppConfig, load_config, validate_stage_environment
# 创建一次运行期间共享的来源、产物、State 和 Plan 容器。
from core.context import ExecutionContext
# 创建所有 Stage 共用的 OpenAI-compatible Chat Completions 适配器。
from core.model import OpenAIModel
# 创建隔离运行目录，并记录事件和最终产物。
from core.recorder import Recorder, create_run_id


# 统一约束每个 `stages/*.py: run()` 的四个输入和字典输出。
StageRunner = Callable[[AppConfig, OpenAIModel, Any, ExecutionContext], dict[str, Any]]


# 将配置中的 Stage 名称映射到对应的 Python 模块；这里只登记入口，不执行模块。
STAGE_MODULES = {
    "s0_api": "stages.s0_api",  # S0：一次普通文本模型调用。
    "s1_structured": "stages.s1_structured",  # S1：严格 DeckSpec JSON。
    "s2_tools": "stages.s2_tools",  # S2：有边界的 Tool Calling。
    "s3_workflow": "stages.s3_workflow",  # S3：代码控制的固定 Workflow。
    "s4_agent": "stages.s4_agent",  # S4：模型控制的 Agent Loop。
    "s5_state": "stages.s5_state",  # S5：显式且可验证的 TaskState。
    "s6_planning": "stages.s6_planning",  # S6：Planning 与 Re-planning。
    "s7_reflection": "stages.s7_reflection",  # S7：检查、修订和复查循环。
}


def _load_runner(stage: str) -> StageRunner:
    """配置校验通过后，动态导入所选阶段的 `run()`。首次使用：S0。"""

    # 根据上方白名单导入当前 Stage，避免一次加载所有阶段实现。
    module = importlib.import_module(STAGE_MODULES[stage])
    # 读取模块约定的统一 `run()` 入口；缺失时先返回 None 供下一步检查。
    runner = getattr(module, "run", None)
    # 防止 Stage 文件存在但没有实现可调用入口。
    if not callable(runner):
        raise RuntimeError(f"Stage 模块缺少 run()：{STAGE_MODULES[stage]}")
    # 把已经验证为可调用的 Stage 入口交还给主流程。
    return runner


def main() -> int:
    """加载配置、创建运行目录并执行一个指定阶段。首次使用：S0。"""

    # 在进入 try 前保留空记录器，供异常分支判断运行目录是否已经创建。
    recorder: Recorder | None = None
    try:
        # 以当前文件所在目录作为 `src` 根目录，不依赖用户执行命令时的 cwd。
        src_dir = Path(__file__).resolve().parent
        # 固定读取 `src/config.yaml`，从而保持 `python src/run.py` 零参数执行。
        config = load_config(src_dir / "config.yaml")
        # S0/S1 检查 active profile 的 URL/密钥；S2–S7 还会检查 Tavily 密钥与工具能力。
        validate_stage_environment(config)
        # 将配置中的输出目录解析为 `src` 内的安全绝对路径。
        output_root = config.resolve_path(str(config.section("run")["output_dir"]))
        # 该字段在正常配置中必填；这里保留运行时防御检查。
        if output_root is None:
            raise RuntimeError("run.output_dir 不能为空")
        # 用 UTC 时间和配置名称生成不覆盖历史结果的唯一运行 ID。
        run_id = create_run_id(str(config.section("run")["run_name"]))
        # 创建 `src/runs/<run_id>/`，后续事件和产物都限制在该目录内。
        recorder = Recorder(output_root / run_id, config.stage)
        # 按配置决定是否复制本次运行的完整配置，便于录屏结果复现。
        if config.section("recording").get("save_config_snapshot", True):
            recorder.write_text("config.snapshot.yaml", config.config_path.read_text(encoding="utf-8"))
        # 写入运行开始事件，记录 run_id 和所选 Stage。
        recorder.record("run_started", run_id=run_id, stage=config.stage)
        # 初始化统一模型接口；模型请求和响应也会写入同一个 Recorder。
        model = OpenAIModel(config, recorder)
        # 创建本次运行共享上下文；S0/S1 只使用基础字段，后续阶段逐步填充更多状态。
        context = ExecutionContext(config=config, recorder=recorder, run_dir=recorder.run_dir)
        # S0/S1 尚未引入 Tool，因此明确不创建 ToolRegistry。
        if config.stage in {"s0_api", "s1_structured"}:
            registry = None
        else:
            # 从 S2 起才延迟导入工具运行时，保证早期 Stage 不隐藏 Tool 能力。
            from core.runtime import build_tool_registry

            # 注册完整小型工具集；具体 Stage 仍会只暴露允许使用的工具子集。
            registry = build_tool_registry(config)
        # 动态加载当前 Stage 的 run()，并传入统一的配置、模型、工具和上下文。
        result = _load_runner(config.stage)(config, model, registry, context)
        # 将 Stage 返回的结构化结果保存为本次运行的统一结果文件。
        recorder.write_json("result.json", result)
        # 在事件流中明确标记主流程成功结束。
        recorder.record("run_finished", status="completed")
        # 向终端打印运行目录和结果，方便用户立即定位生成文件。
        print(json.dumps({"run_dir": str(recorder.run_dir), "result": result}, ensure_ascii=False, indent=2))
        # 返回 0，表示进程执行成功。
        return 0
    except Exception as exc:
        # 已创建 Recorder 表示错误发生在运行目录创建之后，可以保存完整失败记录。
        if recorder is not None:
            # 用与成功路径相同的文件名保存结构化错误结果。
            recorder.write_json("result.json", {"status": "error", "error": str(exc)})
            # 把失败状态和错误信息追加到事件时间线。
            recorder.record("run_finished", status="error", error=str(exc))
            # 在标准错误流中同时提示错误原因和可供排查的运行目录。
            print(f"运行失败：{exc}\n运行记录：{recorder.run_dir}", file=sys.stderr)
        else:
            # 配置、路径或密钥在创建运行目录前失败时，只输出简洁启动错误。
            print(f"启动失败：{exc}", file=sys.stderr)
        # 返回 1，表示进程执行失败。
        return 1


# 只有直接执行 `python src/run.py` 时才启动；被测试或其他模块导入时不自动运行。
if __name__ == "__main__":
    # 将 main() 的返回值转换为操作系统可见的退出码。
    raise SystemExit(main())
