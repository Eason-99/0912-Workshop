"""持久化可观察的事件时间线和每次运行产物。首次使用：S0。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class Recorder:
    """写入只追加事件流以及具名 JSON/文本产物。首次使用：S0。"""

    def __init__(self, run_dir: Path, stage: str) -> None:
        """创建本次运行目录并初始化事件文件路径。首次使用：S0。"""

        self.run_dir = run_dir
        self.stage = stage
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.events_path = self.run_dir / "events.jsonl"

    def record(self, event_type: str, **payload: Any) -> None:
        """追加一条带 UTC 时间且可序列化为 JSON 的事件。首次使用：S0。"""

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self.stage,
            "event_type": event_type,
            **payload,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def write_json(self, relative_path: str, value: Any) -> Path:
        """在本次运行目录内写入格式化 JSON 产物。首次使用：S0。"""

        path = self._artifact_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
        self.record("artifact_written", path=str(path.relative_to(self.run_dir)))
        return path

    def write_text(self, relative_path: str, value: str) -> Path:
        """在本次运行目录内写入 UTF-8 文本产物。首次使用：S0。"""

        path = self._artifact_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        self.record("artifact_written", path=str(path.relative_to(self.run_dir)))
        return path

    def _artifact_path(self, relative_path: str) -> Path:
        """解析产物路径，并拒绝写出当前运行目录。首次使用：S0。"""

        path = (self.run_dir / relative_path).resolve()
        if path != self.run_dir and self.run_dir not in path.parents:
            raise ValueError(f"产物路径越界：{relative_path}")
        return path


def create_run_id(run_name: str) -> str:
    """生成包含 UTC 时间且适合文件系统的运行 ID。首次使用：S0。"""

    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in run_name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{timestamp}_{safe_name}"
