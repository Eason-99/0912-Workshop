"""实现 Tavily 搜索和公开 HTML 网页正文读取。首次使用：S2。"""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

from core.config import AppConfig


class ResearchToolError(RuntimeError):
    """表示需要作为 Observation 返回的搜索或读页错误。首次使用：S2。"""


def _source_id(url: str) -> str:
    """根据 URL 生成稳定且较短的来源 ID。首次使用：S2。"""

    return "src_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _allowed_url(url: str, blocked_domains: list[str]) -> bool:
    """只允许未命中屏蔽域名的 HTTP(S) URL。首次使用：S2。"""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    hostname = (parsed.hostname or "").lower()
    return not any(hostname == item or hostname.endswith("." + item) for item in blocked_domains)


def search_web(query: str, config: AppConfig, date_range: str = "") -> dict[str, Any]:
    """调用 Tavily 并标准化候选结果，但不把摘要视为证据。首次使用：S2。"""

    try:
        import requests
    except ImportError as exc:
        raise ResearchToolError("缺少 requests；请安装 src/requirements.txt") from exc

    research = config.section("research")
    payload: dict[str, Any] = {
        "api_key": config.credential("research", "search_api_key_env"),
        "query": query,
        "max_results": int(research.get("max_results_per_query", 5)),
        "search_depth": "advanced",
        "include_answer": False,
        "include_raw_content": False,
    }
    preferred = research.get("preferred_domains", [])
    if preferred:
        payload["include_domains"] = preferred
    if date_range:
        payload["time_range"] = date_range
    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=30)
        response.raise_for_status()
        raw = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ResearchToolError(f"搜索失败：{exc}") from exc

    blocked = [str(item).lower() for item in research.get("blocked_domains", [])]
    results: list[dict[str, Any]] = []
    for item in raw.get("results", []):
        url = str(item.get("url", ""))
        if not _allowed_url(url, blocked):
            continue
        results.append(
            {
                "source_id": _source_id(url),
                "title": str(item.get("title", "")),
                "url": url,
                "snippet": str(item.get("content", "")),
                "score": item.get("score"),
                "status": "candidate_only",
            }
        )
    return {"query": query, "date_range": date_range, "results": results}


def read_page(url: str, config: AppConfig, source_id: str = "") -> dict[str, Any]:
    """读取公开 HTML 页面，提取并截断可见正文。首次使用：S3。"""

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise ResearchToolError("缺少 requests/beautifulsoup4；请安装 src/requirements.txt") from exc

    research = config.section("research")
    blocked = [str(item).lower() for item in research.get("blocked_domains", [])]
    if not _allowed_url(url, blocked):
        raise ResearchToolError(f"不允许读取该 URL：{url}")
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "WorkshopResearchAgent/1.0"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ResearchToolError(f"网页读取失败：{exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        raise ResearchToolError(f"暂不支持非 HTML 内容：{content_type}")
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    max_chars = int(research.get("max_page_chars", 12000))
    published = ""
    date_meta = soup.find("meta", attrs={"property": "article:published_time"}) or soup.find(
        "meta", attrs={"name": "date"}
    )
    if date_meta and date_meta.get("content"):
        published = str(date_meta["content"])
    return {
        "source_id": source_id or _source_id(url),
        "url": url,
        "title": title,
        "published_at": published,
        "text": text[:max_chars],
        "truncated": len(text) > max_chars,
        "status": "page_read",
    }
