"""保存一次执行共享的运行目录、来源和阶段状态。首次使用：S0。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.config import AppConfig
from core.contracts import PlanState, TaskState
from core.recorder import Recorder


@dataclass
class ExecutionContext:
    """保存一次运行共享的产物位置及逐阶段增加的数据。首次使用：S0。"""

    config: AppConfig
    recorder: Recorder
    run_dir: Path
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    deck: dict[str, Any] | None = None
    state: TaskState | None = None
    plan: PlanState | None = None
    deck_version: int = 0
    tool_call_count: int = 0

    def persist_sources(self) -> None:
        """把当前标准化来源集合写入 `sources.json`。首次使用：S2。"""

        self.recorder.write_json("sources.json", list(self.sources.values()))

    def persist_evidence(self) -> None:
        """把模型从已读来源中提取的证据写入文件。首次使用：S3。"""

        self.recorder.write_json("evidence.json", self.evidence)

    def persist_state(self) -> None:
        """启用 State 后把经过验证的任务状态写入文件。首次使用：S5。"""

        if self.state is not None:
            self.recorder.write_json("state.json", self.state.to_dict())

    def persist_plan(self) -> None:
        """启用 Plan 后把当前计划及修订历史写入文件。首次使用：S6。"""

        if self.plan is not None:
            self.recorder.write_json("plan.json", self.plan.to_dict())
