"""
MCP Web Search & Page Fetch Server — 100% Free / No API Key Required.
Compatible with MCP SDK v1 and v2 (DuckDuckGo Lite).

Install:
    pip install mcp httpx

Run:
    python server.py
"""

import json
import os
import re
import signal
import sys
import urllib.parse
from html.parser import HTMLParser
import httpx


def _handle_exit(sig=None, frame=None):
    """Exit cleanly with return code 0 on SIGTERM/SIGINT so MCP supervisors (e.g. agy) don't error."""
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(0)


signal.signal(signal.SIGTERM, _handle_exit)
signal.signal(signal.SIGINT, _handle_exit)

# Compatibility layer for MCP 2.x and MCP 1.x
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

mcp = MCPServer("web-search")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://lite.duckduckgo.com/",
}

SAFE_SEARCH_MAP = {
    "strict": "1",
    "moderate": "-2",
    "off": "-1",
}

# Patterns to strip accidental tokens/keys before transmission
SENSITIVE_DATA_PATTERNS = [
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\b(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{24,}\b",
    r"\b[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}[- ]?[0-9]{4}\b",
]


def sanitize_query(query: str) -> tuple[str, bool]:
    """Strips accidental private credentials or emails from queries before transmission."""
    sanitized = query
    redacted = False
    for pattern in SENSITIVE_DATA_PATTERNS:
        if re.search(pattern, sanitized, flags=re.IGNORECASE):
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
            redacted = True
    return sanitized.strip(), redacted


def _resolve_url(href: str) -> str:
    """Extract destination URL from DuckDuckGo wrapper links."""
    if not href:
        return ""
    if href.startswith("//"):
        href = f"https:{href}"
    if "duckduckgo.com/l/?" in href or href.startswith("/l/?"):
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query:
            return query["uddg"][0]
    return href


class DDGLiteParser(HTMLParser):
    """Parses DDG Lite table rows while preserving 1:1 result alignment."""

    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._in_link = False
        self._in_snippet = False
        self._link_text: list[str] = []
        self._snippet_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = dict(attrs)
        class_name = attr_dict.get("class", "") or ""

        if tag == "a" and "result-link" in class_name:
            self._commit_current()
            self._current = {
                "title": "",
                "url": _resolve_url(attr_dict.get("href", "") or ""),
                "snippet": "",
            }
            self._in_link = True
            self._link_text = []
        elif tag == "td" and "result-snippet" in class_name:
            self._in_snippet = True
            self._snippet_text = []

    def handle_endtag(self, tag: str):
        if tag == "a" and self._in_link:
            self._in_link = False
            if self._current:
                self._current["title"] = " ".join("".join(self._link_text).split())
        elif tag == "td" and self._in_snippet:
            self._in_snippet = False
            if self._current:
                self._current["snippet"] = " ".join("".join(self._snippet_text).split())

    def handle_data(self, data: str):
        if self._in_link:
            self._link_text.append(data)
        elif self._in_snippet:
            self._snippet_text.append(data)

    def _commit_current(self):
        if self._current and self._current.get("url") and self._current.get("title"):
            title = self._current["title"].strip()
            url = self._current["url"].strip()

            is_nav = any(n in title.lower() for n in ["next page", "more at duckduckgo"])
            is_ad = any(bad in url for bad in ["duckduckgo.com/y.js", "ad_domain", "ad_provider"])

            if not is_nav and not is_ad:
                self.results.append(self._current)

        self._current = None

    def close(self):
        self._commit_current()
        super().close()


class HTMLToMarkdownExtractor(HTMLParser):
    """Converts HTML page content into clean Markdown for LLMs."""

    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []
        self._ignore_depth = 0
        self._current_href: str | None = None
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_dict = dict(attrs)
        if tag in ("script", "style", "noscript", "svg", "header", "footer", "nav", "aside"):
            self._ignore_depth += 1
            return

        if self._ignore_depth > 0:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.chunks.append(f"\n\n{'#' * int(tag[1])} ")
        elif tag in ("p", "div", "article", "section"):
            self.chunks.append("\n\n")
        elif tag == "br":
            self.chunks.append("\n")
        elif tag == "li":
            self.chunks.append("\n* ")
        elif tag == "pre":
            self._in_pre = True
            self.chunks.append("\n```\n")
        elif tag == "code" and not self._in_pre:
            self.chunks.append("`")
        elif tag == "a":
            href = attr_dict.get("href", "")
            if href and not href.startswith(("#", "javascript:")):
                self._current_href = href
                self.chunks.append("[")

    def handle_endtag(self, tag: str):
        if tag in ("script", "style", "noscript", "svg", "header", "footer", "nav", "aside"):
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return

        if self._ignore_depth > 0:
            return

        if tag == "pre":
            self._in_pre = False
            self.chunks.append("\n```\n")
        elif tag == "code" and not self._in_pre:
            self.chunks.append("`")
        elif tag == "a" and self._current_href:
            self.chunks.append(f"]({self._current_href})")
            self._current_href = None
        elif tag in ("p", "div", "article", "section", "h1", "h2", "h3", "h4"):
            self.chunks.append("\n")

    def handle_data(self, data: str):
        if self._ignore_depth == 0:
            text = data if self._in_pre else " ".join(data.split())
            if text:
                self.chunks.append(text + ("" if self._in_pre else " "))

    def get_markdown(self) -> str:
        raw = "".join(self.chunks)
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", raw).strip()


async def fetch_duckduckgo(
    query: str,
    num_results: int = 10,
    region: str = "wt-wt",
    safe_search: str = "moderate",
    date_filter: str | None = None,
) -> list[dict]:
    """Execute asynchronous DDG Lite request with filtering parameters."""
    clean_q, redacted = sanitize_query(query)

    params = {
        "q": clean_q,
        "kl": region,
        "kp": SAFE_SEARCH_MAP.get(safe_search.lower(), "-2"),
    }
    if date_filter:
        params["df"] = date_filter

    url = f"https://lite.duckduckgo.com/lite/?{urllib.parse.urlencode(params)}"

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=12.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code in (403, 429):
                return [{"error": "DuckDuckGo temporarily rate-limited requests from this IP."}]
            resp.raise_for_status()
            html = resp.text
    except httpx.TimeoutException:
        return [{"error": "Search request timed out after 12 seconds."}]
    except httpx.HTTPStatusError as e:
        return [{"error": f"Search failed with HTTP {e.response.status_code}."}]
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]

    parser = DDGLiteParser()
    parser.feed(html)
    parser.close()

    seen: set[str] = set()
    deduped: list[dict] = []

    if redacted:
        deduped.append({"privacy_notice": "Sensitive credentials were automatically redacted from your search query."})

    for item in parser.results:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        deduped.append(item)
        if len(deduped) >= num_results:
            break

    return deduped if deduped else [{"message": "No results found. Try different keywords or regions."}]


@mcp.tool()
async def web_search(
    query: str,
    num_results: int = 10,
    site: str | None = None,
    region: str = "wt-wt",
    safe_search: str = "moderate",
) -> str:
    """
    Search the web using DuckDuckGo with regional and content filtering.

    Args:
        query: The search query string.
        num_results: Number of results to return (default: 10, max: 20).
        site: Optional domain restriction (e.g., 'github.com', 'cve.mitre.org').
        region: Region code (e.g., 'wt-wt' for worldwide, 'us-en', 'uk-en', 'de-de'). Default: 'wt-wt'.
        safe_search: Content filtering level — 'strict', 'moderate', or 'off'. Default: 'moderate'.

    Returns:
        JSON string containing search results with title, URL, and snippet.
    """
    limit = min(max(num_results, 1), 20)
    full_query = f"site:{site} {query}" if site else query
    results = await fetch_duckduckgo(
        query=full_query,
        num_results=limit,
        region=region,
        safe_search=safe_search,
    )
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def search_news(
    query: str,
    num_results: int = 10,
    recency: str = "w",
    region: str = "wt-wt",
    safe_search: str = "moderate",
) -> str:
    """
    Search recent news articles using DuckDuckGo's chronological date filters.

    Args:
        query: The news topic to search for.
        num_results: Number of results to return (default: 10, max: 20).
        recency: Freshness window — 'd' (past day), 'w' (past week), 'm' (past month). Default: 'w'.
        region: Region code (default: 'wt-wt').
        safe_search: Filter level — 'strict', 'moderate', or 'off'. Default: 'moderate'.

    Returns:
        JSON string containing recent news items with title, URL, and snippet.
    """
    limit = min(max(num_results, 1), 20)
    valid_recency = recency if recency in ("d", "w", "m") else "w"
    results = await fetch_duckduckgo(
        query=query,
        num_results=limit,
        region=region,
        safe_search=safe_search,
        date_filter=valid_recency,
    )
    return json.dumps(results, indent=2, ensure_ascii=False)


@mcp.tool()
async def fetch_page(url: str, max_chars: int = 6000) -> str:
    """
    Fetch a webpage found during search and extract its content as structured Markdown.
    Allows LLMs to inspect full articles, documentation, or technical guides.

    Args:
        url: The web URL to fetch and read.
        max_chars: Maximum characters to return (default: 6000, max: 20000).

    Returns:
        Extracted Markdown text from the webpage.
    """
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    max_chars = min(max(max_chars, 500), 20000)

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "").lower()
            if not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml+xml")):
                return f"Skipped: Unsupported media type '{content_type}'. fetch_page only parses web articles and text."

            html = resp.text
    except httpx.TimeoutException:
        return "Error: Webpage request timed out after 15 seconds."
    except httpx.HTTPStatusError as e:
        return f"Error: Webpage returned HTTP {e.response.status_code}."
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"

    extractor = HTMLToMarkdownExtractor()
    extractor.feed(html)
    extractor.close()

    text = extractor.get_markdown()
    if not text:
        return "Warning: No readable text extracted. The page may require client-side JavaScript rendering."

    if len(text) > max_chars:
        return f"{text[:max_chars]}\n\n[...Content truncated at {max_chars} characters...]"

    return text


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    finally:
        _handle_exit()
