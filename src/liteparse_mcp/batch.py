"""
Batch processing helper — parse every PDF in a directory tree.
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from liteparse import LiteParse, search_items

from .imaging import draw_bounding_boxes
from .parser import make_config, page_to_dict


def process_one(
    pdf_path: Path,
    output_dir: Path,
    config,
    search_phrase: Optional[str] = None,
) -> dict:
    out = output_dir / pdf_path.stem
    out.mkdir(parents=True, exist_ok=True)

    result = {"file": str(pdf_path), "pages": 0, "text_items": 0, "error": None}
    try:
        parser = LiteParse(config)
        parse_result = parser.parse(pdf_path)
        result["pages"] = len(parse_result.pages)

        pages_json = []
        for page in parse_result.pages:
            items = page.text_items
            if search_phrase:
                items = search_items(items, search_phrase)
            result["text_items"] += len(items)
            pages_json.append(page_to_dict(page))

        (out / "pages.json").write_text(
            json.dumps(pages_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out / "summary.txt").write_text(parse_result.text, encoding="utf-8")

        shots = parser.screenshot(pdf_path)
        page_map = {p["page_num"]: p for p in pages_json}

        for shot in shots:
            (out / f"page_{shot.page_num}.png").write_bytes(shot.image_bytes)
            if shot.page_num in page_map:
                pd = page_map[shot.page_num]
                proxies = [
                    type("T", (), {
                        "x": ti["x"], "y": ti["y"],
                        "width": ti["width"], "height": ti["height"],
                    })()
                    for ti in pd["text_items"]
                ]
                cited = draw_bounding_boxes(
                    shot.image_bytes, proxies,
                    page_width_pts=pd["width_pts"],
                    page_height_pts=pd["height_pts"],
                    dpi=config.dpi,
                )
                (out / f"page_{shot.page_num}_cited.png").write_bytes(cited)

        print(f"  ✓ {pdf_path.name}  ({result['pages']} pages, {result['text_items']} items)")

    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ✗ {pdf_path.name}  ERROR: {exc}")

    return result


def batch_process(
    input_path: Path,
    output_dir: Path,
    *,
    dpi: float = 150.0,
    ocr_enabled: bool = True,
    max_workers: int = 4,
    search_phrase: Optional[str] = None,
) -> list:
    output_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(input_path.glob("**/*.pdf")) if input_path.is_dir() else [input_path]

    if not pdfs:
        print(f"No PDF files found in {input_path}")
        return []

    config = make_config(dpi=dpi, ocr_enabled=ocr_enabled, num_workers=2)
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(process_one, pdf, output_dir, config, search_phrase): pdf
            for pdf in pdfs
        }
        for future in as_completed(futures):
            results.append(future.result())

    ok_count  = sum(1 for r in results if not r["error"])
    err_count = sum(1 for r in results if r["error"])
    report = {
        "total": len(results),
        "succeeded": ok_count,
        "failed": err_count,
        "files": results,
    }
    (output_dir / "batch_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return results
