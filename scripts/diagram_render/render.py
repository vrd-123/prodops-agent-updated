"""ProdOps diagram renderer.

Renders Jinja2 HTML templates to PNG via Playwright (headless Chromium).
Produces polished, information-rich infographic-style diagrams for
Slack replies — a higher-fidelity alternative to Mermaid.

Usage (CLI):
    python -m scripts.diagram_render.render \\
        --template resolution_flow \\
        --data scripts/diagram_render/examples/resolution_flow_prodops_4567.json \\
        --out reports/samples/prodops_4567.png

Programmatic:
    from scripts.diagram_render.render import render
    render(template="resolution_flow", data=payload, out_path="out.png")

Templates live in ./templates/ as *.html.j2 files.
Each template defines its own JSON schema; see examples/ for schema-by-example.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_HERE = Path(__file__).resolve().parent
_TEMPLATES_DIR = _HERE / "templates"


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "htm", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(template: str, data: dict[str, Any]) -> str:
    """Render the given template name to HTML string."""
    env = _build_env()
    tpl = env.get_template(f"{template}.html.j2")
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        **data,
    }
    return tpl.render(**payload)


def render(
    template: str,
    data: dict[str, Any],
    out_path: str | Path,
    *,
    viewport_width: int = 1200,
    scale: float = 2.0,
) -> Path:
    """Render template to PNG at out_path. Returns the output Path."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    html = render_html(template, data)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Playwright is not installed. Run:\n"
            "    pip install -r scripts/diagram_render/requirements.txt\n"
            "    python -m playwright install chromium"
        ) from exc

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": viewport_width, "height": 900},
                device_scale_factor=scale,
            )
            page = context.new_page()
            page.set_content(html, wait_until="load")
            page.wait_for_load_state("networkidle")
            element = page.query_selector(".page")
            if element is None:
                raise RuntimeError("Template did not produce a .page root element")
            element.screenshot(path=str(out), type="png", omit_background=False)
        finally:
            browser.close()

    return out


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a ProdOps diagram to PNG.")
    parser.add_argument("--template", required=True, help="Template name (e.g. resolution_flow)")
    parser.add_argument("--data", required=True, help="Path to JSON data file")
    parser.add_argument("--out", required=True, help="Output PNG path")
    parser.add_argument("--width", type=int, default=1200, help="Viewport width (default 1200)")
    parser.add_argument("--scale", type=float, default=2.0, help="Device scale factor (default 2.0)")
    args = parser.parse_args(argv)

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"ERROR: data file not found: {data_path}", file=sys.stderr)
        return 2
    data = json.loads(data_path.read_text())

    out = render(
        template=args.template,
        data=data,
        out_path=args.out,
        viewport_width=args.width,
        scale=args.scale,
    )
    print(str(out))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
