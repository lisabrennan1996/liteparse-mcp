"""
LiteParse MCP Server — tool definitions.
All tools are registered on the shared `mcp` FastMCP instance.
"""

import base64
import json
from pathlib import Path
from typing import Annotated, Optional

from fastmcp import FastMCP
from pydantic import Field

from .imaging import draw_bounding_boxes
from .parser import make_config, page_to_dict

from liteparse import LiteParse, LiteParseConfig, search_items

mcp = FastMCP(
    name="liteparse",
    instructions=(
        "Local PDF parsing tools powered by LiteParse (Rust-based, no cloud, no API key). "
        "Use parse_pdf to extract structured text with bounding boxes. "
        "Use screenshot_pdf or cited_screenshot to get visual page images. "
        "Use batch_parse_pdfs to process an entire folder at once. "
        "Use search_pdf to find where a phrase appears with exact page coordinates."
    ),
)


# ---------------------------------------------------------------------------
# parse_pdf
# ---------------------------------------------------------------------------

@mcp.tool
def parse_pdf(
    pdf_path: Annotated[str, Field(description="Absolute path to the PDF file to parse.")],
    pages: Annotated[
        Optional[str],
        Field(description="Comma-separated page numbers, e.g. '1,3,5'. Omit for all pages."),
    ] = None,
    ocr_enabled: Annotated[bool, Field(description="Run OCR on image-based / scanned pages.")] = True,
    dpi: Annotated[float, Field(description="Resolution used internally (affects OCR quality). Default 150.")] = 150.0,
) -> str:
    """
    Parse a PDF and return structured text plus bounding boxes for every
    text item on every page.

    Bounding-box coordinates are in **PDF points** (1 pt = 1/72 inch),
    with the origin at the top-left corner of each page.

    Returns JSON:
        { "pages": [ { "page_num", "width_pts", "height_pts", "text",
                       "text_items": [ { "text", "x", "y", "width", "height",
                                         "font_name", "font_size", "confidence" } ] } ] }
    """
    path = Path(pdf_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {pdf_path}"})

    cfg = make_config(dpi=dpi, ocr_enabled=ocr_enabled)
    if pages:
        cfg = LiteParseConfig(
            ocr_language=cfg.ocr_language, ocr_enabled=cfg.ocr_enabled,
            ocr_server_url=cfg.ocr_server_url, ocr_server_headers=cfg.ocr_server_headers,
            tessdata_path=cfg.tessdata_path, max_pages=cfg.max_pages,
            target_pages=pages, dpi=cfg.dpi, output_format="json",
            preserve_very_small_text=cfg.preserve_very_small_text,
            password=cfg.password, quiet=True, num_workers=cfg.num_workers,
        )

    result = LiteParse(cfg).parse(path)
    return json.dumps({"pages": [page_to_dict(p) for p in result.pages]}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# batch_parse_pdfs
# ---------------------------------------------------------------------------

@mcp.tool
def batch_parse_pdfs(
    folder_path: Annotated[str, Field(description="Absolute path to folder containing PDF files.")],
    output_folder: Annotated[
        Optional[str],
        Field(description="Where to write outputs. Defaults to <folder>/liteparse_output/"),
    ] = None,
    ocr_enabled: Annotated[bool, Field(description="Run OCR on image-based pages.")] = True,
    max_workers: Annotated[int, Field(description="PDFs to process in parallel. Default 4.")] = 4,
) -> str:
    """
    Parse all PDFs in a folder.  For each PDF, writes to
    <output_folder>/<stem>/:
      pages.json        – text + bounding boxes per page
      summary.txt       – plain text of the whole document
      page_N.png        – raw page screenshot
      page_N_cited.png  – screenshot with bounding-box highlights

    Returns a JSON summary of successes and any errors.
    """
    from .batch import batch_process

    folder = Path(folder_path)
    if not folder.is_dir():
        return json.dumps({"error": f"Not a directory: {folder_path}"})

    out = Path(output_folder) if output_folder else folder / "liteparse_output"
    results = batch_process(folder, out, ocr_enabled=ocr_enabled, max_workers=max_workers)

    ok  = [r for r in results if not r.get("error")]
    err = [r for r in results if r.get("error")]
    return json.dumps({
        "output_folder": str(out),
        "total": len(results), "succeeded": len(ok), "failed": len(err),
        "files": results,
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# screenshot_pdf
# ---------------------------------------------------------------------------

@mcp.tool
def screenshot_pdf(
    pdf_path: Annotated[str, Field(description="Absolute path to the PDF file.")],
    page_numbers: Annotated[
        Optional[str],
        Field(description="Comma-separated pages to render, e.g. '1,2'. Omit for all."),
    ] = None,
    dpi: Annotated[float, Field(description="Screenshot resolution in DPI. Default 150.")] = 150.0,
) -> str:
    """
    Render PDF pages as PNG images (base64-encoded).

    Returns JSON list of:
        { "page_num", "width_px", "height_px", "image_base64" }
    """
    path = Path(pdf_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {pdf_path}"})

    pages_list = [int(n.strip()) for n in page_numbers.split(",")] if page_numbers else None
    shots = LiteParse(make_config(dpi=dpi)).screenshot(path, page_numbers=pages_list)

    return json.dumps([
        {
            "page_num": s.page_num,
            "width_px": s.width,
            "height_px": s.height,
            "image_base64": base64.b64encode(s.image_bytes).decode(),
        }
        for s in shots
    ])


# ---------------------------------------------------------------------------
# cited_screenshot
# ---------------------------------------------------------------------------

@mcp.tool
def cited_screenshot(
    pdf_path: Annotated[str, Field(description="Absolute path to the PDF file.")],
    page_number: Annotated[int, Field(description="Page to render (1-based).")] = 1,
    dpi: Annotated[float, Field(description="Screenshot resolution in DPI. Default 150.")] = 150.0,
    highlight_color_rgb: Annotated[
        str,
        Field(description="Highlight colour as 'R,G,B' (0-255 each). Default '255,100,0' (orange)."),
    ] = "255,100,0",
    search_phrase: Annotated[
        Optional[str],
        Field(description="If given, only highlight text items matching this phrase."),
    ] = None,
) -> str:
    """
    Render a single PDF page as a PNG with bounding-box highlights drawn
    over every extracted text item (or only items matching search_phrase).

    Returns JSON:
        { "page_num", "width_px", "height_px", "items_highlighted", "image_base64" }
    """
    path = Path(pdf_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {pdf_path}"})

    try:
        r, g, b = [int(v.strip()) for v in highlight_color_rgb.split(",")]
    except Exception:
        r, g, b = 255, 100, 0

    cfg = make_config(dpi=dpi)
    parser = LiteParse(cfg)
    parse_result = parser.parse(path)
    shots = parser.screenshot(path, page_numbers=[page_number])

    if not shots:
        return json.dumps({"error": f"Page {page_number} not found in {pdf_path}"})

    shot = shots[0]
    page_data = next((p for p in parse_result.pages if p.page_num == page_number), None)
    if page_data is None:
        return json.dumps({"error": f"Could not parse page {page_number}"})

    items = page_data.text_items
    if search_phrase:
        items = search_items(items, search_phrase)

    proxies = [
        type("T", (), {"x": t.x, "y": t.y, "width": t.width, "height": t.height})()
        for t in items
    ]
    cited = draw_bounding_boxes(
        shot.image_bytes, proxies,
        page_width_pts=page_data.width, page_height_pts=page_data.height,
        dpi=dpi, color=(r, g, b, 160),
    )

    return json.dumps({
        "page_num": shot.page_num,
        "width_px": shot.width,
        "height_px": shot.height,
        "items_highlighted": len(proxies),
        "image_base64": base64.b64encode(cited).decode(),
    })


# ---------------------------------------------------------------------------
# search_pdf
# ---------------------------------------------------------------------------

@mcp.tool
def search_pdf(
    pdf_path: Annotated[str, Field(description="Absolute path to the PDF file.")],
    phrase: Annotated[str, Field(description="Text phrase to search for.")],
    case_sensitive: Annotated[bool, Field(description="Case-sensitive match. Default false.")] = False,
) -> str:
    """
    Search for a phrase in a PDF and return every matching text item with its
    page number and bounding-box coordinates.

    Returns JSON:
        { "phrase", "match_count",
          "matches": [ { "page_num", "text", "x", "y", "width", "height", "font_size" } ] }
    """
    path = Path(pdf_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {pdf_path}"})

    result = LiteParse(make_config()).parse(path)
    matches = []
    for page in result.pages:
        for t in search_items(page.text_items, phrase, case_sensitive=case_sensitive):
            matches.append({
                "page_num": page.page_num,
                "text": t.text,
                "x": round(t.x, 2), "y": round(t.y, 2),
                "width": round(t.width, 2), "height": round(t.height, 2),
                "font_size": round(t.font_size, 1) if t.font_size else None,
            })

    return json.dumps({"phrase": phrase, "match_count": len(matches), "matches": matches},
                      ensure_ascii=False)
