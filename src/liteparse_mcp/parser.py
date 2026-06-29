"""
Shared parser helpers — config construction and page serialisation.
"""

from liteparse import LiteParse, LiteParseConfig


def make_config(
    *,
    dpi: float = 150.0,
    ocr_enabled: bool = True,
    num_workers: int = 2,
) -> LiteParseConfig:
    """Return a LiteParseConfig with sensible defaults."""
    defaults = LiteParse().get_config()
    return LiteParseConfig(
        ocr_language=defaults.ocr_language,
        ocr_enabled=ocr_enabled,
        ocr_server_url=defaults.ocr_server_url,
        ocr_server_headers=defaults.ocr_server_headers,
        tessdata_path=defaults.tessdata_path,
        max_pages=defaults.max_pages,
        target_pages=defaults.target_pages,
        dpi=dpi,
        output_format="json",
        preserve_very_small_text=False,
        password=defaults.password,
        quiet=True,
        num_workers=num_workers,
    )


def page_to_dict(page) -> dict:
    """Serialise a ParsedPage to a plain dict."""
    return {
        "page_num": page.page_num,
        "width_pts": page.width,
        "height_pts": page.height,
        "text": page.text,
        "text_items": [
            {
                "text": t.text,
                "x": round(t.x, 2),
                "y": round(t.y, 2),
                "width": round(t.width, 2),
                "height": round(t.height, 2),
                "font_name": t.font_name,
                "font_size": round(t.font_size, 1) if t.font_size else None,
                "confidence": round(t.confidence, 3) if t.confidence else None,
            }
            for t in page.text_items
        ],
    }
