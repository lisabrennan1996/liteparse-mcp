# liteparse-mcp

> Fast, local PDF parsing as an MCP server — text extraction, bounding boxes,
> OCR, and visual citations. No cloud. No API key. Powered by
> [LiteParse](https://developers.llamaindex.ai/liteparse/).

[![PyPI](https://img.shields.io/pypi/v/liteparse-mcp)](https://pypi.org/project/liteparse-mcp/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/liteparse-mcp)](https://pypi.org/project/liteparse-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## Tools

| Tool | Description |
|---|---|
| `parse_pdf` | Extract text + bounding boxes (x, y, width, height in PDF points) from a PDF |
| `batch_parse_pdfs` | Parse every PDF in a folder; write JSON + screenshots per file |
| `screenshot_pdf` | Render pages as base64 PNG images |
| `cited_screenshot` | Render a page with highlight boxes drawn over every text item |
| `search_pdf` | Find a phrase and return all matching positions with coordinates |

Bounding-box coordinates are in **PDF points** (1 pt = 1/72 in), origin top-left.
To convert to pixels: `px = pt × (dpi / 72)`.

---

## Install

```bash
pip install liteparse-mcp
```

---

## Usage

### Claude Desktop

Add to `~/AppData/Roaming/Claude/claude_desktop_config.json` (Windows) or
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "liteparse": {
      "command": "liteparse-mcp"
    }
  }
}
```

Or with the explicit Python path (if `liteparse-mcp` is not on PATH):

```json
{
  "mcpServers": {
    "liteparse": {
      "command": "python",
      "args": ["-m", "liteparse_mcp"]
    }
  }
}
```

Restart Claude Desktop — the five tools appear automatically.

### Claude Code

```bash
claude mcp add liteparse -- python -m liteparse_mcp
```

### HTTP / SSE (for remote agents or testing)

```bash
liteparse-mcp --http
# Server listens on http://127.0.0.1:8765
```

---

## Example agent prompts

- *"Parse report.pdf and show me where 'efficacy' appears with bounding boxes"*
- *"Get a cited screenshot of page 3 of study.pdf"*
- *"Batch parse every PDF in my Downloads folder and save the output"*
- *"Search safety_data.pdf for 'adverse event' and list the page numbers"*

---

## Outputs (batch mode)

For each PDF, `batch_parse_pdfs` writes:

```
<output_folder>/
  <stem>/
    pages.json          # structured JSON: page text + TextItem bounding boxes
    summary.txt         # plain text of the whole document
    page_1.png          # raw page screenshot
    page_1_cited.png    # screenshot with bounding-box highlights
    ...
  batch_report.json     # overall success / error summary
```

---

## Requirements

- Python ≥ 3.10
- `liteparse` ≥ 2.0.0 (Rust-based; wheels available for Windows, macOS, Linux)
- `fastmcp` ≥ 2.0.0

No Tesseract installation required for text-based PDFs.
For scanned PDFs with `ocr_enabled=true`, Tesseract is used automatically
if available on PATH.

---

## License

MIT
