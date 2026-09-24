# DuckDuckGo Web Search & Page Reader MCP Server

<p align="center">
  <img src="https://raw.githubusercontent.com/dev0x194/mcp-server-web-search/main/assets/banner.png" alt="Project Banner" width="100%" />
</p>

<p align="center">
  <em>A fast, free, and privacy-preserving Model Context Protocol (MCP) server providing web search, news retrieval, query sanitization, and clean Markdown page extraction without third-party API keys.</em>
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-Protocol-blue.svg?style=flat-square" alt="MCP Protocol" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-brightgreen.svg?style=flat-square" alt="Python Version" /></a>
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" alt="License" /></a>
  <a href="https://github.com/dev0x194/mcp-server-web-search/stargazers"><img src="https://img.shields.io/github/stars/dev0x194/mcp-server-web-search?style=flat-square" alt="Stars" /></a>
  <a href="https://github.com/dev0x194/mcp-server-web-search/issues"><img src="https://img.shields.io/github/issues/dev0x194/mcp-server-web-search?style=flat-square" alt="Issues" /></a>
</p>

---

<p align="center">
  <img src="https://raw.githubusercontent.com/dev0x194/mcp-server-web-search/main/assets/demo.gif" alt="Animated Demo Preview" width="85%" />
</p>

## Overview

**`mcp-server-web-search`** empowers any LLM or AI agent (Claude Desktop, Google Antigravity / Gemini CLI, Cursor, Continue.dev, etc.) with real-time web awareness. Built on top of DuckDuckGo Lite, it eliminates recurring SaaS subscription costs, rate-limit headaches, and API key configurations while prioritizing developer and data privacy.

Whether your agent needs to search current technical documentation, look up recent news, or read deep-dive articles in structured Markdown, this server delivers fast, sanitized, and LLM-ready responses out of the box.

---

## Key Features

- **100% Free & No API Keys Required**: Seamless web retrieval without subscribing to search engine API tiers or managing secret tokens.
- **Three Specialized MCP Tools**:
  - `web_search`: General web search with domain-specific targeting (`site:`), international region selection, and safe search controls.
  - `search_news`: Recency-filtered news discovery across past day (`d`), week (`w`), or month (`m`).
  - `fetch_page`: Deep webpage scraper that discards layout noise (headers, footers, scripts, sidebars) and converts readable article content into clean Markdown.
- **Automated Query Sanitization & Privacy Shield**: Outgoing queries are automatically inspected via regex to redact accidentally leaked API credentials (GitHub, OpenAI, Stripe, AWS), credit card numbers, and email addresses before they touch the network.
- **Dual MCP SDK Compatibility**: Seamlessly runs on both `mcp` 1.x (`FastMCP`) and modern `mcp` 2.x (`MCPServer`) without code modifications.
- **Production-Grade Process Lifecycle**: Fully implements clean POSIX signal handlers (`SIGTERM`, `SIGINT`) and immediate EOF shutdowns to guarantee clean exit codes (`0`) during client configuration reloads and process restarts.

---

## Available Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `web_search` | `query` *(str)*, `num_results` *(int, default: 10)*, `site` *(str, optional)*, `region` *(str, default: 'wt-wt')*, `safe_search` *(str, default: 'moderate')* | Searches DuckDuckGo Lite and returns JSON results containing title, URL, and snippet. |
| `search_news` | `query` *(str)*, `num_results` *(int, default: 10)*, `recency` *(str: 'd', 'w', 'm')*, `region` *(str)*, `safe_search` *(str)* | Searches recent news articles with strict chronological filters. |
| `fetch_page` | `url` *(str)*, `max_chars` *(int, default: 6000, max: 20000)* | Fetches and parses web HTML into structured, token-efficient Markdown for LLM ingestion. |

---

## Prerequisites

- **Python 3.10+** (Tested on Python 3.10, 3.11, 3.12, 3.13, and 3.14)
- **pip** or **uv** package manager
- Any MCP-compliant client (Claude Desktop, Gemini CLI / Antigravity, Cursor, etc.)

---

## Installation

Clone the repository and set up a Python virtual environment:

```bash
# Clone the repository
git clone https://github.com/dev0x194/mcp-server-web-search.git
cd mcp-server-web-search

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install mcp httpx
```

*Or using [uv](https://github.com/astral-sh/uv) for lightning-fast installation:*

```bash
uv venv
source .venv/bin/activate
uv pip install mcp httpx
```

---

## Client Configuration

Add the server to your preferred MCP client configuration file:

### 1. Claude Desktop

Edit your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "web-search": {
      "command": "/absolute/path/to/mcp-server-web-search/.venv/bin/python",
      "args": [
        "/absolute/path/to/mcp-server-web-search/server.py"
      ]
    }
  }
}
```

### 2. Google Antigravity / Gemini CLI

Edit `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "web-search": {
      "command": "/absolute/path/to/mcp-server-web-search/.venv/bin/python",
      "args": [
        "/absolute/path/to/mcp-server-web-search/server.py"
      ],
      "disabled": false
    }
  }
}
```

### 3. Cursor IDE

Navigate to **Cursor Settings > Features > MCP**, click **Add New MCP Server**, and enter:
- **Name**: `web-search`
- **Type**: `stdio`
- **Command**: `/absolute/path/to/mcp-server-web-search/.venv/bin/python /absolute/path/to/mcp-server-web-search/server.py`

---

## Quick Start & Verification

You can verify that the server boots and responds to the stdio protocol directly from your command line:

```bash
python server.py
```

### Example Usage from an LLM

Once loaded into your MCP client, the assistant will automatically leverage the tools:

#### 1. Targeted Technical Search
> **User**: *"Find the latest security advisories for Next.js on github.com."*  
> **Assistant Call**:
> ```json
> {
>   "name": "web_search",
>   "arguments": {
>     "query": "security advisories vulnerabilities",
>     "site": "github.com/vercel/next.js"
>   }
> }
> ```

#### 2. Chronological News Lookup
> **User**: *"What happened with SpaceX launches over the past week?"*  
> **Assistant Call**:
> ```json
> {
>   "name": "search_news",
>   "arguments": {
>     "query": "SpaceX launch Falcon 9 Starship",
>     "recency": "w"
>   }
> }
> ```

#### 3. Reading Full Web Documentation
> **User**: *"Fetch the official Python asyncio task group documentation and summarize it."*  
> **Assistant Call**:
> ```json
> {
>   "name": "fetch_page",
>   "arguments": {
>     "url": "https://docs.python.org/3/library/asyncio-task.html",
>     "max_chars": 8000
>   }
> }
> ```

---

## Development & Testing

Run the server with test inputs or execute manual health checks:

```bash
# Run unit checks on query sanitization and extractor
python3 -c "from server import sanitize_query; print(sanitize_query('Check user@example.com token ghp_123456789012345678901234567890123456'))"
```

---

## Contributing

Contributions make the open-source community an incredible place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. **Fork the Project**
2. **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit your Changes** (`git commit -m 'Add some AmazingFeature'`)
4. **Push to the Branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

Please ensure all PRs follow clean code principles and preserve backwards compatibility with MCP SDK v1 and v2.

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more details.

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/dev0x194">dev0x194</a> and the Open Source AI community.
</p>
