"""
Searcher 的工具：web_search、fetch_page。
每个工具返回结构化 dict: {"success": bool, "data": ..., "error": str | None}
"""
import json
import logging

import os

logger = logging.getLogger(__name__)

RESEARCH_DIR = os.path.join("deliverables", "research")
os.makedirs(RESEARCH_DIR, exist_ok=True)


def web_search(query: str, max_results: int = 5) -> str:
    """
    搜索互联网，返回结果列表。

    Args:
        query (str): 搜索关键词
        max_results (int): 最多返回几条结果，默认 5

    Returns:
        str: JSON 字符串，格式 {"success": true, "results": [...], "query": "..."}
    """
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        results = []
        # ddgs 在某些网络环境下可能不稳定，尝试两次
        for attempt in range(2):
            try:
                for r in ddgs.text(query=query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
                break
            except Exception:
                if attempt == 0:
                    continue
                raise
        logger.info("web_search: query='%s', got %d results", query, len(results))
        return json.dumps({"success": True, "results": results, "query": query}, ensure_ascii=False)
    except Exception as e:
        logger.error("web_search failed: %s", e)
        return json.dumps({"success": False, "results": [], "error": str(e)}, ensure_ascii=False)


def fetch_page(url: str) -> str:
    """
    抓取网页内容并提取纯文本（去 HTML 标签）。

    策略：
    1. 先尝试用完整浏览器 headers 抓取
    2. 如果 403/拒绝，降级到仅保留核心 headers 再试一次
    3. 超时自动重试一次

    Args:
        url (str): 网页 URL

    Returns:
        str: JSON 字符串，格式 {"success": true, "text": "...", "url": "..."}
    """
    import urllib.request
    import re

    headers_full = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    headers_minimal = {"User-Agent": headers_full["User-Agent"]}

    raw = None
    last_error = None

    # 策略 1：完整 headers
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=headers_full)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                continue

    # 策略 2：如果完整 headers 失败，尝试 minimal headers
    if raw is None:
        try:
            req = urllib.request.Request(url, headers=headers_minimal)
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            last_error = e

    if raw is None:
        logger.error("fetch_page failed for %s: %s", url, last_error)
        return json.dumps({"success": False, "text": "", "error": str(last_error)}, ensure_ascii=False)

    # 简易 HTML 去标签 + 截断
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text[:8000]  # 最多 8000 字符，防止炸上下文

    logger.info("fetch_page: url='%s', got %d chars", url, len(text))
    return json.dumps({"success": True, "text": text, "url": url}, ensure_ascii=False)


def save_report(filename: str, content: str) -> str:
    """
    把调研报告保存为 deliverables/research/ 下的 Markdown 文件。

    Args:
        filename (str): 文件名，如 "async_framework_comparison.md"
        content (str): Markdown 格式的报告内容

    Returns:
        str: JSON 字符串 {"success": true, "filepath": "..."}
    """
    try:
        filepath = os.path.join(RESEARCH_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        size = len(content.encode("utf-8"))
        logger.info("save_report: wrote %d bytes to %s", size, filepath)
        return json.dumps(
            {"success": True, "filepath": os.path.abspath(filepath), "size": size},
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("save_report failed: %s", e)
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
