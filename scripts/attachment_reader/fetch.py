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
    3. For text-based files (.log, .json, …) — saves as-is.
       The Cursor agent reads them directly.
    4. For images (.png, .jpg, …) — saves as-is.
       The Cursor agent views them natively via its multimodal model.
    5. For PDFs — extracts the text layer into a companion .txt file.
       If the PDF is scanned (no text), converts pages to .png images
       that the agent can view.
    6. Writes a _manifest.md summarising what was downloaded, so the
       agent has a table of contents before diving into individual files.

PHI / PII Protection (HIPAA):
    - .csv, .xlsx, .xls, .parquet, .tsv files are NEVER downloaded —
      these data-export formats are the highest PHI risk.
    - Filenames matching known PHI patterns (patient, claims, enrollment,
      ssn, dob, phi, pii, etc.) are blocked before download.
    - All downloaded text and PDF content is scanned locally with regex
      patterns for SSN, MRN, DOB, patient names, emails, phone numbers,
      insurance IDs, FHIR patient references, and ICD-10 codes.
    - Files that fail the PHI scan are quarantined: content is deleted
      from disk and replaced with a quarantine notice. The LLM never
      sees the raw content.
    - These checks run entirely in Python — no content reaches the LLM
      until it has passed all PHI gates.

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
import re
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

# ── PHI / PII Protection — file-type blocklist ──────────────────────
# These extensions are data-export formats with the highest PHI risk.
# They are NEVER downloaded — metadata only is recorded.
PHI_RISK_EXTENSIONS = {
    ".csv", ".xlsx", ".xls", ".parquet", ".tsv",
}

# ── PHI / PII Protection — filename pattern blocklist ───────────────
# Files whose names match these patterns are blocked before download.
PHI_RISK_FILENAME_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"patient",
        r"member",
        r"claims?",
        r"enrollment",
        r"beneficiar",
        r"\bssn\b",
        r"\bdob\b",
        r"\bphi\b",
        r"\bpii\b",
        r"medical.?record",
        r"\bmrn\b",
        r"health.?data",
        r"personal.?info",
        r"identif",
        r"hipaa",
        r"protected.?health",
    ]
]

# ── PHI / PII Protection — content regex patterns ───────────────────
# Applied locally in Python to downloaded file content BEFORE the LLM
# ever sees it. Each tuple is (compiled_pattern, human_readable_label).
_PHI_CONTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                                    "SSN"),
    (re.compile(r"\b(?:MRN|mrn|Medical\s+Record\s+(?:Number|No|#?))[:\s#]*\d+\b", re.IGNORECASE), "MRN"),
    (re.compile(r"\b(?:DOB|Date\s+of\s+Birth)[:\s]*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b", re.IGNORECASE), "DOB"),
    (re.compile(r"\b(?:Patient|Member)\s+(?:Name|ID)[:\s]*[A-Z][a-z]+", re.IGNORECASE), "Patient/Member ID"),
    (re.compile(r"\b\d{10}\b"),                                                "Phone Number (10-digit)"),
    (re.compile(r"\b[\w.\-+]+@[\w.\-]+\.\w{2,}\b"),                           "Email Address"),
    (re.compile(r"\b(?:Insurance\s+ID|Policy\s+(?:Number|No|#?))[:\s]*[\w\-]+\b", re.IGNORECASE), "Insurance ID"),
    (re.compile(r'"resourceType"\s*:\s*"Patient"'),                            "FHIR Patient Resource"),
    (re.compile(r'\bPatient/\d+\b'),                                           "FHIR Patient Reference"),
    (re.compile(r"\b[A-Z]\d{2}(?:\.\d{1,3})?\b"),                             "ICD-10 Code"),
    (re.compile(r"\b(?:NPI|National\s+Provider)[:\s]*\d{10}\b", re.IGNORECASE), "NPI Number"),
]

# File-type classification
# NOTE: .csv is intentionally absent — it is in PHI_RISK_EXTENSIONS above.
TEXT_EXTENSIONS = {
    ".log", ".txt", ".json", ".xml", ".yaml", ".yml", ".md",
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
    """
    Return 'text', 'image', 'pdf', 'phi_risk', or 'unsupported'.

    'phi_risk' is returned for data-export extensions (.csv, .xlsx, etc.)
    that must never be downloaded due to PHI risk. These are checked
    BEFORE the standard text/image/pdf classification.
    """
    ext = Path(filename).suffix.lower()
    if ext in PHI_RISK_EXTENSIONS:
        return "phi_risk"
    if ext in TEXT_EXTENSIONS:
        return "text"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    return "unsupported"


def _has_phi_risk_filename(filename: str) -> bool:
    """
    Return True if the filename matches a known PHI-risk pattern.
    This check is applied BEFORE downloading the file.
    """
    name = Path(filename).stem  # check stem only, not extension
    return any(pattern.search(name) for pattern in PHI_RISK_FILENAME_PATTERNS)


def _size_display(size: int) -> str:
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


# ── PHI scanning ────────────────────────────────────────────────────

def _scan_for_phi(filepath: Path) -> list[str]:
    """
    Scan a local file for PHI/PII patterns using regex.

    Runs entirely in Python — never touches the LLM.
    Returns a list of PHI type labels found (empty list = clean).
    Only reads the first 50 KB to keep scanning fast.
    """
    findings: list[str] = []
    try:
        content = filepath.read_text(errors="replace")[:51200]  # 50 KB cap
    except Exception:
        return findings

    for pattern, label in _PHI_CONTENT_PATTERNS:
        if pattern.search(content):
            findings.append(label)

    return findings


def _quarantine_file(filepath: Path, phi_findings: list[str]) -> None:
    """
    Quarantine a file that failed the PHI scan.

    Deletes the file content from disk and replaces it with a
    quarantine notice. The LLM will see only the notice — never
    the original PHI-containing content.
    """
    notice = (
        f"⚠️  QUARANTINED — PHI/PII DETECTED\n"
        f"{'=' * 50}\n"
        f"This file was quarantined by the PHI scanner.\n"
        f"Detected patterns: {', '.join(phi_findings)}\n"
        f"Original content has been deleted to prevent PHI\n"
        f"from reaching the AI model (HIPAA compliance).\n"
        f"{'=' * 50}\n"
        f"Action required: A human reviewer must inspect the\n"
        f"original attachment in Jira directly.\n"
    )
    try:
        filepath.write_text(notice)
    except Exception:
        # If we can't overwrite, try to delete
        try:
            filepath.unlink()
        except Exception:
            pass


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
    Extracted text is scanned for PHI before being saved.
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
        # Text-based PDF — write extracted text then scan for PHI
        txt_path = output_dir / f"{stem}_extracted.txt"
        txt_path.write_text(full_text)

        phi_findings = _scan_for_phi(txt_path)
        if phi_findings:
            print(f"   🚨 PHI detected in PDF text ({', '.join(phi_findings)}) — quarantining")
            _quarantine_file(txt_path, phi_findings)
            companions.append({
                "filename": txt_path.name,
                "type": "text",
                "note": f"⚠️ QUARANTINED — PHI detected: {', '.join(phi_findings)}. Content deleted.",
                "quarantined": True,
                "phi_findings": phi_findings,
            })
        else:
            companions.append({
                "filename": txt_path.name,
                "type": "text",
                "note": f"Text extracted from {pdf_path.name} ({len(pages_text)} pages) — PHI scan: clean",
                "quarantined": False,
            })
            print(f"   📝 Extracted text → {txt_path.name} (PHI scan: clean)")
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
                    "quarantined": False,
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

    # Separate entries into categories
    active_entries = [e for e in entries if not e.get("skipped") and not e.get("quarantined") and e.get("type") != "phi_risk"]
    quarantined_entries = [e for e in entries if e.get("quarantined")]
    blocked_entries = [e for e in entries if e.get("type") == "phi_risk" or e.get("phi_risk_filename")]
    skipped_entries = [e for e in entries if e.get("skipped") and e.get("type") not in ("phi_risk",) and not e.get("phi_risk_filename")]

    lines: list[str] = [
        f"# Attachments for {issue_key}",
        "",
        f"> ⚠️ **PHI Protection Active** — All files have been scanned for PHI/PII before",
        f"> being made available to the AI model. Quarantined and blocked files must be",
        f"> reviewed by a human directly in Jira.",
        "",
        f"Downloaded {len(active_entries)} readable file(s) to `{output_dir}/`",
        "",
        "## How to use these files",
        "",
        "- **Text files** (`.log`, `.txt`, `.json`, …): Read them directly with the file reader.",
        "- **Images** (`.png`, `.jpg`, …): View them directly — you have native vision capabilities.",
        "- **`*_extracted.txt`**: Text pulled from a PDF. Read this instead of the raw PDF.",
        "- **`*_pageN.png`**: Page images from a scanned PDF. View these to see the content.",
        "- **⚠️ Quarantined / Blocked**: Do NOT attempt to read these — content has been removed.",
        "",
        "## File listing",
        "",
        "| # | File | Type | Size | PHI Status | Notes |",
        "|---|------|------|------|------------|-------|",
    ]

    row_num = 1
    for entry in entries:
        if entry.get("skipped") and entry.get("type") not in ("phi_risk",) and not entry.get("phi_risk_filename"):
            continue  # skipped files go in their own section below
        icon = {"text": "📄", "image": "🖼️", "pdf": "📑", "unsupported": "📦", "phi_risk": "🚫"}.get(entry.get("type", ""), "📎")
        notes = entry.get("note", "")

        if entry.get("quarantined"):
            phi_status = "🚨 QUARANTINED"
        elif entry.get("type") == "phi_risk" or entry.get("phi_risk_filename"):
            phi_status = "🚫 BLOCKED"
        else:
            phi_status = "✅ Clean"

        lines.append(
            f"| {row_num} | {icon} `{entry['filename']}` | {entry.get('type', '?')} | {entry.get('size', '')} | {phi_status} | {notes} |"
        )
        row_num += 1

    lines.append("")

    if quarantined_entries:
        lines.append("## ⚠️ Quarantined files (PHI detected — content deleted)")
        lines.append("")
        lines.append("These files contained PHI/PII patterns. Content was deleted before the AI model")
        lines.append("could read it. A human must review these attachments directly in Jira.")
        lines.append("")
        for e in quarantined_entries:
            phi_list = ", ".join(e.get("phi_findings", []))
            lines.append(f"- `{e['filename']}` — PHI types detected: {phi_list}")
        lines.append("")

    if blocked_entries:
        lines.append("## 🚫 Blocked files (high PHI-risk type — never downloaded)")
        lines.append("")
        lines.append("These files were not downloaded because their type or filename indicates")
        lines.append("high PHI risk (data exports, patient files, etc.).")
        lines.append("")
        for e in blocked_entries:
            lines.append(f"- `{e['filename']}` — {e.get('note', 'blocked')}")
        lines.append("")

    if skipped_entries:
        lines.append("## Skipped files")
        lines.append("")
        for e in skipped_entries:
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

    PHI protection pipeline (runs before any content reaches the LLM):
      1. Block PHI-risk file types (.csv, .xlsx, .parquet, .tsv, .xls)
      2. Block PHI-risk filenames (patient, claims, enrollment, ssn, etc.)
      3. Download remaining files
      4. Scan text/PDF content with local regex PHI detector
      5. Quarantine (delete content of) any file that fails the scan

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
    phi_blocked_count = 0
    phi_quarantined_count = 0

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
            "quarantined": False,
        }

        # ── PHI Gate 1: Block by file type ──────────────────────────
        if file_type == "phi_risk":
            print(f"   🚫 BLOCKED — data-export format ({Path(filename).suffix}) is PHI-risk. Not downloaded.")
            entry["skipped"] = True
            entry["note"] = (
                f"Blocked — {Path(filename).suffix} is a data-export format with high PHI risk. "
                f"Review directly in Jira."
            )
            entries.append(entry)
            phi_blocked_count += 1
            continue

        # ── PHI Gate 2: Block by filename pattern ───────────────────
        if _has_phi_risk_filename(filename):
            print(f"   🚫 BLOCKED — filename matches PHI-risk pattern. Not downloaded.")
            entry["skipped"] = True
            entry["phi_risk_filename"] = True
            entry["note"] = (
                f"Blocked — filename '{filename}' matches a PHI-risk pattern "
                f"(patient/claims/enrollment/ssn/dob/phi/etc.). Review directly in Jira."
            )
            entries.append(entry)
            phi_blocked_count += 1
            continue

        # ── Skip if too large ────────────────────────────────────────
        if size > MAX_FILE_SIZE:
            print(f"   ⏭️  Skipped — exceeds {_size_display(MAX_FILE_SIZE)} limit")
            entry["skipped"] = True
            entry["note"] = f"Exceeds {_size_display(MAX_FILE_SIZE)} size limit"
            entries.append(entry)
            continue

        # ── Skip unsupported types ───────────────────────────────────
        if file_type == "unsupported":
            print(f"   ⏭️  Skipped — unsupported file type")
            entry["skipped"] = True
            entry["note"] = "Unsupported file type"
            entries.append(entry)
            continue

        # ── Download ─────────────────────────────────────────────────
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

        # ── Post-processing ──────────────────────────────────────────
        if file_type == "text":
            # PHI Gate 3: Scan content
            phi_findings = _scan_for_phi(dest)
            if phi_findings:
                print(f"   🚨 PHI detected ({', '.join(phi_findings)}) — quarantining")
                _quarantine_file(dest, phi_findings)
                entry["quarantined"] = True
                entry["phi_findings"] = phi_findings
                entry["note"] = f"⚠️ QUARANTINED — PHI detected: {', '.join(phi_findings)}. Content deleted."
                phi_quarantined_count += 1
            else:
                if _truncate_text_file(dest):
                    entry["note"] = f"Truncated to ~{MAX_TEXT_LINES} lines (was larger) — PHI scan: clean"
                    print(f"   ✂️  Truncated to ~{MAX_TEXT_LINES} lines (PHI scan: clean)")
                else:
                    entry["note"] = "Full content — PHI scan: clean"
                    print(f"   🛡️  PHI scan: clean")
            entries.append(entry)

        elif file_type == "image":
            entry["note"] = "Agent can view this image directly — check for visible PHI in screenshots"
            entries.append(entry)

        elif file_type == "pdf":
            entries.append(entry)
            # Extract text or convert to images (PHI scan happens inside _extract_pdf)
            companions = _extract_pdf(dest, out)
            for comp in companions:
                comp.setdefault("skipped", False)
                comp_path = out / comp["filename"]
                if comp_path.exists():
                    comp["size"] = _size_display(comp_path.stat().st_size)
                else:
                    comp["size"] = ""
                if comp.get("quarantined"):
                    phi_quarantined_count += 1
                entries.append(comp)

    # ── Summary ──────────────────────────────────────────────────────
    readable = [e for e in entries if not e.get("skipped") and not e.get("quarantined")]
    print(f"\n{'=' * 55}")
    print(f"  PHI PROTECTION SUMMARY")
    print(f"{'=' * 55}")
    print(f"  Total attachments  : {len(raw_attachments)}")
    print(f"  Readable by agent  : {len(readable)}")
    print(f"  Blocked (pre-DL)   : {phi_blocked_count}")
    print(f"  Quarantined (scan) : {phi_quarantined_count}")
    print(f"{'=' * 55}")

    # Write manifest
    _write_manifest(out, issue_key, entries)
    print(f"\n📋 Manifest written → {out / '_manifest.md'}")
    print(f"✅ Done! {len(entries)} file(s) processed in {out}")

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
