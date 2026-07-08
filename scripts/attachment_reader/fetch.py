#!/usr/bin/env python3
"""
fetch.py — Download & pre-process Jira ticket attachments.

Downloads every attachment on a ticket into a local folder so the
Cursor agent can read text files and view images natively — with
zero need for a separate vision API key.

Usage:
    python scripts/attachment_reader/fetch.py PRODOPS-42
    python scripts/attachment_reader/fetch.py PRODOPS-42 --output-dir workspace/attachments

What it does:
    1. Calls the Jira REST API to list attachments on the ticket.
    2. Downloads each file to  workspace/attachments/{TICKET}/
    3. For text-based files (.log, .csv, .json, …) — saves as-is.
       The Cursor agent reads them directly.
    4. For images (.png, .jpg, …) — saves as-is.
       The Cursor agent views them natively via its multimodal model.
    5. For PDFs — extracts the text layer into a companion .txt file.
       If the PDF is scanned (no text), converts pages to .png images
       that the agent can view.
    6. Writes a _manifest.md summarising what was downloaded, so the
       agent has a table of contents before diving into individual files.

Environment variables (set in .env at repo root):
    JIRA_BASE_URL       e.g. https://abacusinsights.atlassian.net
    JIRA_USER_EMAIL     your Atlassian login email
    JIRA_API_TOKEN      API token from id.atlassian.com
      — OR —
    JIRA_PAT            Personal Access Token (Data Center)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# ── Try loading .env ────────────────────────────────────────────────

def _load_dotenv() -> None:
    """Best-effort .env loading — no hard dependency on python-dotenv."""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        # Manual fallback: parse KEY=VALUE lines
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and value:
                    os.environ.setdefault(key, value)


_load_dotenv()


# ── Configuration ───────────────────────────────────────────────────

JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
JIRA_USER_EMAIL = os.environ.get("JIRA_USER_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PAT = os.environ.get("JIRA_PAT", "")

# Limits
MAX_FILE_SIZE = int(os.environ.get("ATTACHMENT_MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10 MB
MAX_TEXT_LINES = int(os.environ.get("ATTACHMENT_MAX_TEXT_LINES", 500))

# File-type classification
TEXT_EXTENSIONS = {
    ".log", ".txt", ".csv", ".json", ".xml", ".yaml", ".yml", ".md",
    ".sh", ".py", ".conf", ".cfg", ".ini", ".env", ".tf", ".hcl",
    ".toml", ".properties", ".sql", ".html", ".htm",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg"}
PDF_EXTENSIONS = {".pdf"}


# ── Auth helpers ────────────────────────────────────────────────────

def _auth_header() -> dict[str, str]:
    """Build the Authorization header for Jira."""
    if JIRA_PAT:
        return {"Authorization": f"Bearer {JIRA_PAT}"}
    if JIRA_USER_EMAIL and JIRA_API_TOKEN:
        creds = base64.b64encode(
            f"{JIRA_USER_EMAIL}:{JIRA_API_TOKEN}".encode()
        ).decode()
        return {"Authorization": f"Basic {creds}"}
    print("❌ Error: Set JIRA_USER_EMAIL + JIRA_API_TOKEN  or  JIRA_PAT", file=sys.stderr)
    sys.exit(1)


def _jira_get(path: str) -> dict:
    """GET a Jira REST endpoint and return parsed JSON."""
    url = f"{JIRA_BASE_URL}{path}"
    headers = {**_auth_header(), "Accept": "application/json"}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"❌ Jira API error ({e.code}): {url}", file=sys.stderr)
        if e.code == 401:
            print("   → Check your JIRA_USER_EMAIL + JIRA_API_TOKEN", file=sys.stderr)
        elif e.code == 404:
            print("   → Issue not found. Check the ticket key.", file=sys.stderr)
        sys.exit(1)


def _jira_download(url: str, dest: Path) -> None:
    """Download a file from Jira (authenticated)."""
    headers = _auth_header()
    req = Request(url, headers=headers)
    with urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


# ── File classification ─────────────────────────────────────────────

def _classify(filename: str) -> str:
    """Return 'text', 'image', 'pdf', or 'unsupported'."""
    ext = Path(filename).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return "text"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    return "unsupported"


def _size_display(size: int) -> str:
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


# ── Text processing ─────────────────────────────────────────────────

def _truncate_text_file(filepath: Path) -> bool:
    """
    If a text file exceeds MAX_TEXT_LINES, truncate to head + tail
    and rewrite in place. Returns True if truncated.
    """
    try:
        lines = filepath.read_text(errors="replace").splitlines()
    except Exception:
        return False

    if len(lines) <= MAX_TEXT_LINES:
        return False

    head_count = MAX_TEXT_LINES * 3 // 4  # 75% from top
    tail_count = MAX_TEXT_LINES - head_count  # 25% from bottom
    omitted = len(lines) - head_count - tail_count

    truncated = (
        lines[:head_count]
        + [f"", f"... [{omitted:,} lines omitted — file was {len(lines):,} lines] ...", f""]
        + lines[-tail_count:]
    )
    filepath.write_text("\n".join(truncated))
    return True


# ── PDF processing ──────────────────────────────────────────────────

def _extract_pdf(pdf_path: Path, output_dir: Path) -> list[dict]:
    """
    Extract text from a PDF. If scanned, convert pages to images.
    Returns a list of created companion files as dicts.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print(f"   ⚠️  PyMuPDF not installed — skipping PDF text extraction for {pdf_path.name}")
        print(f"      Install with: pip install PyMuPDF")
        return []

    companions: list[dict] = []
    stem = pdf_path.stem

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"   ⚠️  Failed to open PDF {pdf_path.name}: {e}")
        return []

    # Try text extraction
    pages_text: list[str] = []
    for i, page in enumerate(doc):
        pages_text.append(page.get_text())

    full_text = "\n\n--- Page Break ---\n\n".join(pages_text).strip()
    total_chars = len(full_text.replace("\n", "").replace(" ", ""))
    avg_chars = total_chars / max(len(pages_text), 1)

    if avg_chars >= 50:
        # Text-based PDF — write extracted text
        txt_path = output_dir / f"{stem}_extracted.txt"
        txt_path.write_text(full_text)
        companions.append({
            "filename": txt_path.name,
            "type": "text",
            "note": f"Text extracted from {pdf_path.name} ({len(pages_text)} pages)",
        })
        print(f"   📝 Extracted text → {txt_path.name}")
    else:
        # Scanned PDF — convert pages to images for agent to view
        print(f"   🔍 PDF appears scanned (avg {avg_chars:.0f} chars/page) — converting to images")
        for i, page in enumerate(doc):
            if i >= 5:  # cap at 5 pages
                print(f"   ⚠️  Capped at 5 page images")
                break
            try:
                pix = page.get_pixmap(dpi=150)
                img_path = output_dir / f"{stem}_page{i+1}.png"
                pix.save(str(img_path))
                companions.append({
                    "filename": img_path.name,
                    "type": "image",
                    "note": f"Page {i+1} of scanned PDF {pdf_path.name}",
                })
                print(f"   🖼️  Page {i+1} → {img_path.name}")
            except Exception as e:
                print(f"   ⚠️  Failed to render page {i+1}: {e}")

    doc.close()
    return companions


# ── Manifest generation ─────────────────────────────────────────────

def _write_manifest(
    output_dir: Path,
    issue_key: str,
    entries: list[dict],
) -> None:
    """Write _manifest.md — the agent reads this first to know what's available."""
    lines: list[str] = [
        f"# Attachments for {issue_key}",
        "",
        f"Downloaded {len(entries)} file(s) to `{output_dir}/`",
        "",
        "## How to use these files",
        "",
        "- **Text files** (`.log`, `.txt`, `.csv`, `.json`, …): Read them directly with the file reader.",
        "- **Images** (`.png`, `.jpg`, …): View them directly — you have native vision capabilities.",
        "- **`*_extracted.txt`**: Text pulled from a PDF. Read this instead of the raw PDF.",
        "- **`*_pageN.png`**: Page images from a scanned PDF. View these to see the content.",
        "",
        "## File listing",
        "",
        "| # | File | Type | Size | Notes |",
        "|---|------|------|------|-------|",
    ]

    for i, entry in enumerate(entries, 1):
        icon = {"text": "📄", "image": "🖼️", "pdf": "📑", "unsupported": "📦"}.get(entry["type"], "📎")
        notes = entry.get("note", "")
        lines.append(
            f"| {i} | {icon} `{entry['filename']}` | {entry['type']} | {entry.get('size', '')} | {notes} |"
        )

    lines.append("")

    skipped = [e for e in entries if e.get("skipped")]
    if skipped:
        lines.append("## Skipped files")
        lines.append("")
        for e in skipped:
            lines.append(f"- `{e['filename']}` — {e.get('note', 'unsupported type')}")
        lines.append("")

    (output_dir / "_manifest.md").write_text("\n".join(lines))


# ── Main fetch logic ────────────────────────────────────────────────

def fetch_attachments(
    issue_key: str,
    output_dir: Optional[str] = None,
) -> Path:
    """
    Download and pre-process all attachments for a Jira ticket.

    Returns the path to the output directory.
    """
    if not JIRA_BASE_URL:
        print("❌ JIRA_BASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    # Resolve output directory
    if output_dir:
        out = Path(output_dir) / issue_key
    else:
        repo_root = Path(__file__).resolve().parents[2]
        out = repo_root / "workspace" / "attachments" / issue_key
    out.mkdir(parents=True, exist_ok=True)

    print(f"🔍 Fetching attachments for {issue_key}...")
    data = _jira_get(f"/rest/api/3/issue/{issue_key}?fields=attachment")
    raw_attachments = data.get("fields", {}).get("attachment") or []

    if not raw_attachments:
        print(f"   ℹ️  No attachments found on {issue_key}")
        _write_manifest(out, issue_key, [])
        return out

    print(f"   Found {len(raw_attachments)} attachment(s)")

    entries: list[dict] = []

    for att in raw_attachments:
        filename = att.get("filename", "unknown")
        size = int(att.get("size", 0))
        content_url = att.get("content", "")
        file_type = _classify(filename)

        print(f"\n   📎 {filename} ({_size_display(size)}, {file_type})")

        entry: dict = {
            "filename": filename,
            "type": file_type,
            "size": _size_display(size),
            "skipped": False,
        }

        # Skip if too large
        if size > MAX_FILE_SIZE:
            print(f"   ⏭️  Skipped — exceeds {_size_display(MAX_FILE_SIZE)} limit")
            entry["skipped"] = True
            entry["note"] = f"Exceeds {_size_display(MAX_FILE_SIZE)} size limit"
            entries.append(entry)
            continue

        # Skip unsupported types
        if file_type == "unsupported":
            print(f"   ⏭️  Skipped — unsupported file type")
            entry["skipped"] = True
            entry["note"] = "Unsupported file type"
            entries.append(entry)
            continue

        # Download
        dest = out / filename
        try:
            _jira_download(content_url, dest)
            print(f"   ✅ Downloaded → {dest.name}")
        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            entry["skipped"] = True
            entry["note"] = f"Download error: {e}"
            entries.append(entry)
            continue

        # Post-processing
        if file_type == "text":
            if _truncate_text_file(dest):
                entry["note"] = f"Truncated to ~{MAX_TEXT_LINES} lines (was larger)"
                print(f"   ✂️  Truncated to ~{MAX_TEXT_LINES} lines")
            else:
                entry["note"] = "Full content"
            entries.append(entry)

        elif file_type == "image":
            entry["note"] = "Agent can view this image directly"
            entries.append(entry)

        elif file_type == "pdf":
            entries.append(entry)
            # Extract text or convert to images
            companions = _extract_pdf(dest, out)
            for comp in companions:
                comp["skipped"] = False
                comp["size"] = _size_display((out / comp["filename"]).stat().st_size)
                entries.append(comp)

    # Write manifest
    _write_manifest(out, issue_key, entries)
    print(f"\n📋 Manifest written → {out / '_manifest.md'}")
    print(f"✅ Done! {len(entries)} file(s) in {out}")

    return out


# ── CLI entry point ─────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Jira ticket attachments for the ProdOps agent."
    )
    parser.add_argument("issue_key", help="Jira issue key, e.g. PRODOPS-42")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Custom output directory (default: workspace/attachments/)",
    )
    args = parser.parse_args()
    fetch_attachments(args.issue_key, args.output_dir)


if __name__ == "__main__":
    main()
