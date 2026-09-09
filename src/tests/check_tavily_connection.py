"""使用真实 `.env` 测试 Tavily 搜索工具是否可用。首次使用：S2。"""

from __future__ import annotations

import json
from pathlib import Path
import sys


# 允许直接执行 `python src/tests/check_tavily_connection.py` 时导入 src 内模块。
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config import load_config  # noqa: E402
from tools.research import search_web  # noqa: E402


def main() -> int:
    """加载正式配置并执行一次真实搜索，输出不包含 API Key 的结果摘要。首次使用：S2。"""

    try:
        config = load_config(SRC_DIR / "config.yaml")
        result = search_web(
            "中国大陆 AI 助手 App 最新发展",
            config,
            date_range="month",
        )
        summary = {
            "success": True,
            "provider": config.section("research")["search_provider"],
            "query": result["query"],
            "result_count": len(result["results"]),
            "results": [
                {
                    "title": item["title"],
                    "url": item["url"],
                    "source_id": item["source_id"],
                }
                for item in result["results"][:3]
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1


# 仅在直接运行脚本时请求 Tavily，普通 unittest discover 不会产生联网调用。
if __name__ == "__main__":
    raise SystemExit(main())
