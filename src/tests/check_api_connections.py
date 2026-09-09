"""使用真实 `.env` 逐一检查两个 profile 的 Responses API 连通性。首次使用：S0。"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any
from urllib.parse import urlparse


# 允许直接执行 `python src/tests/check_api_connections.py` 时导入 src 内模块。
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import AppConfig, load_config  # noqa: E402


def _exception_chain(exc: Exception) -> str:
    """整理真实连接测试的异常链，方便区分 DNS、TLS、超时和 HTTP 错误。首次使用：S0。"""

    parts: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(parts) < 6:
        parts.append(f"{type(current).__name__}: {str(current).strip() or '无详细信息'}")
        current = current.__cause__ or current.__context__
    return " <- ".join(parts)


def check_profile(config: AppConfig, profile_name: str) -> dict[str, Any]:
    """对一个 profile 发起最小 Responses 请求并返回脱敏结果。首次使用：S0。"""

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("缺少 openai；请先安装 src/requirements.txt") from exc

    profile = config.section("model")["profiles"][profile_name]
    api_key, base_url = config.model_connection(profile_name)
    started_at = time.monotonic()
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=float(config.section("model").get("timeout_seconds", 120)),
            max_retries=int(config.section("model").get("max_retries", 3)),
        )
        with client.responses.stream(
            model=str(profile["name"]),
            input="这是 API 连通性测试。请只回复 OK。",
            max_output_tokens=32,
        ) as stream:
            response = stream.get_final_response()
        return {
            "profile": profile_name,
            "success": True,
            "api_mode": "responses",
            "streaming": True,
            "model": str(profile["name"]),
            "host": urlparse(base_url).hostname,
            "status": getattr(response, "status", None),
            "output_length": len(str(getattr(response, "output_text", "") or "")),
            "elapsed_seconds": round(time.monotonic() - started_at, 2),
        }
    except Exception as exc:
        return {
            "profile": profile_name,
            "success": False,
            "api_mode": "responses",
            "streaming": True,
            "model": str(profile["name"]),
            "host": urlparse(base_url).hostname,
            "elapsed_seconds": round(time.monotonic() - started_at, 2),
            "error": _exception_chain(exc),
        }


def main() -> int:
    """依次测试 config.yaml 中的全部模型 profile，并打印 JSON 摘要。首次使用：S0。"""

    config = load_config(SRC_DIR / "config.yaml")
    profile_names = list(config.section("model")["profiles"])
    results = [check_profile(config, profile_name) for profile_name in profile_names]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(result["success"] for result in results) else 1


# 仅在直接运行该脚本时产生真实 API 请求，普通 unittest discover 不会调用它。
if __name__ == "__main__":
    raise SystemExit(main())
