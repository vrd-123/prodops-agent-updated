---
name: attachment-reader
description: Fetch and read Jira ticket attachments. Downloads files to workspace/attachments/{TICKET}/ so you can read text files and view images natively — no external vision API needed.
triggers:
  - attachment
  - attachments
  - attached file
  - screenshot
  - log file
  - uploaded file
---

# Attachment Reader Skill

## When to use

Use this skill whenever you need to examine files attached to a Jira ticket — screenshots, log files, CSVs, PDFs, config files, etc.

## How it works

You have **native vision capabilities**. You can read text files and view images directly. This skill simply downloads the attachments from Jira to a local folder so you can access them.

## Step-by-step

### Step 1 — Download attachments

Run the fetch script in the terminal:

```bash
python scripts/attachment_reader/fetch.py {ISSUE_KEY}
```

This creates `workspace/attachments/{ISSUE_KEY}/` with:
- The raw attachment files (images, text files, etc.)
- `_manifest.md` — a table of contents listing every file
- `*_extracted.txt` — text pulled from any PDFs
- `*_pageN.png` — page images from scanned PDFs (no text layer)

### Step 2 — Read the manifest

Read `workspace/attachments/{ISSUE_KEY}/_manifest.md` to see what was downloaded and what type each file is.

### Step 3 — Process each file by type

| File type | What to do |
|-----------|------------|
| **Text** (`.log`, `.txt`, `.csv`, `.json`, …) | Read the file directly with the file reader. Look for errors, stack traces, config issues. |
| **Image** (`.png`, `.jpg`, …) | View the image directly — you can see it natively. Describe what you observe (error dialogs, UI state, charts). |
| **PDF extracted text** (`*_extracted.txt`) | Read the extracted text file. This is the text layer from the PDF. |
| **Scanned PDF pages** (`*_pageN.png`) | View each page image. These are rendered pages from a scanned PDF. |
| **Skipped** | Check the manifest for the skip reason. Mention to the user that these files couldn't be processed. |

### Step 4 — Incorporate into analysis

Include the attachment content in your analysis. When generating reports for the validation/triage/remedy hooks, reference specific details from attachments:
- Quote error messages from log files
- Describe what screenshots show (error dialogs, UI states, configuration screens)
- Reference data from CSV/JSON files
- Note any attachments that were skipped

## Example

```
User: Respond to ticket PRODOPS-142

Agent:
1. Runs: python scripts/attachment_reader/fetch.py PRODOPS-142
2. Reads: workspace/attachments/PRODOPS-142/_manifest.md
3. Reads: workspace/attachments/PRODOPS-142/airflow_error.log
4. Views: workspace/attachments/PRODOPS-142/dag_screenshot.png
5. Proceeds with validation → triage → remedy using full context
```

## Prerequisites

- `.env` file at repo root with `JIRA_BASE_URL` + auth credentials (see `.env.example`)
- Optional: `pip install PyMuPDF` for PDF processing
