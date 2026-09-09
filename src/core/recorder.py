"""持久化可观察的事件时间线和每次运行产物。首次使用：S0。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class Recorder:
    """写入只追加事件流以及具名 JSON/文本产物。首次使用：S0。"""

    def __init__(self, run_dir: Path, stage: str) -> None:
        """创建运行目录，并初始化事件与模型调用索引路径。首次使用：S0。"""

        self.run_dir = run_dir
        self.stage = stage
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.events_path = self.run_dir / "events.jsonl"
        self.model_calls_path = self.run_dir / "model_calls.jsonl"

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

    def record_model_request(
        self,
        call_id: str,
        call_number: int,
        profile: str,
        api_mode: str,
        request: dict[str, Any],
    ) -> Path:
        """保存最终 API 请求，并把 request 阶段追加到统一调用日志。首次使用：S0。"""

        relative_path = f"model_calls/{call_id}_request.json"
        request_path = self.write_json(relative_path, request)
        self._append_model_call(
            {
                "call_id": call_id,
                "call_number": call_number,
                "phase": "request",
                "profile": profile,
                "api_mode": api_mode,
                "request": request,
                "request_path": relative_path,
            }
        )
        self.record(
            "model_request",
            call_id=call_id,
            call_number=call_number,
            profile=profile,
            api_mode=api_mode,
            request_path=str(request_path.relative_to(self.run_dir)),
        )
        return request_path

    def record_model_response(
        self,
        call_id: str,
        call_number: int,
        response_id: str,
        status: str | None,
        output_text: str,
        provider_response: Any,
        save_provider_response: bool,
    ) -> None:
        """保存原始输出与可选完整响应，并追加 response 阶段记录。首次使用：S0。"""

        output_relative_path = f"model_calls/{call_id}_output.txt"
        output_path = self.write_text(output_relative_path, output_text)
        response_relative_path: str | None = None
        if save_provider_response:
            response_relative_path = f"model_calls/{call_id}_response.json"
            self.write_json(response_relative_path, provider_response)
        self._append_model_call(
            {
                "call_id": call_id,
                "call_number": call_number,
                "phase": "response",
                "response_id": response_id,
                "status": status,
                "output_text": output_text,
                "output_path": output_relative_path,
                "response_path": response_relative_path,
            }
        )
        self.record(
            "model_response",
            call_id=call_id,
            call_number=call_number,
            response_id=response_id,
            status=status,
            output_path=str(output_path.relative_to(self.run_dir)),
            response_path=response_relative_path,
        )

    def record_model_error(
        self,
        call_id: str,
        call_number: int,
        profile: str,
        api_mode: str,
        error: str,
    ) -> None:
        """把失败调用追加到统一调用日志和运行事件流。首次使用：S0。"""

        payload = {
            "call_id": call_id,
            "call_number": call_number,
            "phase": "error",
            "profile": profile,
            "api_mode": api_mode,
            "error": error,
        }
        self._append_model_call(payload)
        self.record("model_error", **payload)

    def _append_model_call(self, payload: dict[str, Any]) -> None:
        """向统一 `model_calls.jsonl` 追加带时间和 Stage 的一条记录。首次使用：S0。"""

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self.stage,
            **payload,
        }
        with self.model_calls_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

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
