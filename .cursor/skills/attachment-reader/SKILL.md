---
name: attachment-reader
description: Fetch and read Jira ticket attachments. Downloads files to workspace/attachments/{TICKET}/ so you can read text files and view images natively — no external vision API needed. All files are scanned for PHI/PII before being made available to the agent.
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

Use this skill whenever you need to examine files attached to a Jira ticket — screenshots, log files, PDFs, config files, etc.

> ⚠️ **PHI/PII Protection is built into this skill.** The fetch script automatically
> blocks high-risk file types, scans all downloaded content for PHI patterns, and
> quarantines any file that contains PHI before the agent reads it. You MUST respect
> these protections — see Step 2.5 below.

## How it works

You have **native vision capabilities**. You can read text files and view images directly. This skill downloads the attachments from Jira to a local folder so you can access them — after they have passed the PHI protection pipeline.

## Step-by-step

### Step 1 — Download attachments

Run the fetch script in the terminal:

```bash
python scripts/attachment_reader/fetch.py {ISSUE_KEY}
```

This creates `workspace/attachments/{ISSUE_KEY}/` with:
- The raw attachment files (images, text files, etc.) — **PHI-scanned and clean**
- `_manifest.md` — a table of contents listing every file with its PHI status
- `*_extracted.txt` — text pulled from any PDFs (PHI-scanned)
- `*_pageN.png` — page images from scanned PDFs (no text layer)

The script will print a **PHI Protection Summary** at the end showing how many files
were blocked, quarantined, and made available to the agent.

### Step 2 — Read the manifest

Read `workspace/attachments/{ISSUE_KEY}/_manifest.md` to see what was downloaded,
what type each file is, and its **PHI Status** column:

| PHI Status | Meaning | What to do |
|------------|---------|------------|
| ✅ Clean | Passed PHI scan | Read/view normally |
| 🚨 QUARANTINED | PHI detected — content deleted | **DO NOT read** — note it in output |
| 🚫 BLOCKED | High-risk type or filename — never downloaded | **DO NOT attempt to fetch** — note it in output |

---

### Step 2.5 — PHI Pre-Check (MANDATORY — DO NOT SKIP)

Before reading ANY file from the manifest, apply these rules:

1. **Quarantined files** — If a file is marked `🚨 QUARANTINED` in the manifest,
   **do NOT open or read it**. The content has been deleted. Include this note in
   your output:
   > "⚠️ Attachment `{filename}` was quarantined — potential PHI detected
   > ({phi_types}). A human reviewer must inspect this file directly in Jira."

2. **Blocked files** — If a file is marked `🚫 BLOCKED`, **do NOT attempt to
   download or read it**. Include this note in your output:
   > "⚠️ Attachment `{filename}` was blocked (high PHI-risk type/filename).
   > Review directly in Jira."

3. **Text files — first-10-lines check** — Even for files marked ✅ Clean, read
   the first 10 lines before proceeding. If you observe any of the following,
   STOP reading and flag the file for manual review:
   - Social Security Numbers (###-##-####)
   - Medical Record Numbers (MRN, MRN#, Medical Record)
   - Dates of Birth (DOB, Date of Birth)
   - Patient or Member names/IDs
   - Insurance policy numbers

4. **Images / screenshots** — You MAY view images. However, **do NOT describe,
   transcribe, or quote** any patient-identifiable information visible in the
   image (names, MRNs, DOBs, account numbers visible in UI fields). If you see
   PHI in a screenshot, note: "Screenshot contains potentially identifiable
   information — redacted per HIPAA policy."

5. **PDF extracted text** (`*_extracted.txt`) — Treat the same as text files.
   Apply the first-10-lines check before reading in full.

6. **Never bypass fetch.py** — Do NOT use any other method (curl, wget, direct
   Jira API calls) to download attachment content. All downloads must go through
   `fetch.py` so the PHI pipeline runs.

---

### Step 3 — Process each file by type

| File type | PHI Status | What to do |
|-----------|------------|------------|
| **Text** (`.log`, `.txt`, `.json`, …) | ✅ Clean | Read the file. Look for errors, stack traces, config issues. |
| **Text** | 🚨 QUARANTINED | Do NOT read. Note quarantine in output. |
| **Image** (`.png`, `.jpg`, …) | ✅ Clean | View the image. Describe what you observe (error dialogs, UI state, charts). Do NOT describe visible PHI. |
| **PDF extracted text** (`*_extracted.txt`) | ✅ Clean | Read the extracted text. |
| **PDF extracted text** | 🚨 QUARANTINED | Do NOT read. Note quarantine in output. |
| **Scanned PDF pages** (`*_pageN.png`) | ✅ Clean | View each page image. |
| **Blocked** (`.csv`, `.xlsx`, PHI filename) | 🚫 BLOCKED | Do NOT read. Note block in output. |
| **Skipped** | N/A | Check the manifest for the skip reason. Mention to the user. |

### Step 4 — Incorporate into analysis

Include the attachment content in your analysis. When generating reports for the
validation/triage/remedy hooks, reference specific details from attachments:
- Quote error messages from log files
- Describe what screenshots show (error dialogs, UI states, configuration screens)
- Reference data from JSON/config files
- Note any attachments that were quarantined, blocked, or skipped

### Step 5 — Report PHI findings

Always include a **PHI Protection Summary** section in your output when attachments
were processed:

```
## Attachment PHI Protection Summary
- Total attachments: N
- Readable by agent: N
- Blocked (pre-download): N  [list filenames]
- Quarantined (PHI scan): N  [list filenames + PHI types detected]
- Action required: [list any files needing human review]
```

If all files were clean, a one-liner is sufficient:
> "All N attachments passed PHI scan — no sensitive data detected."

---

## Architecture: PHI Protection Layers

```
Jira Attachment
      │
      ▼
[Layer 1] Block by extension (.csv/.xlsx/.parquet/.tsv/.xls)
      │  → phi_risk: metadata only, never downloaded
      ▼
[Layer 2] Block by filename pattern (patient/claims/ssn/dob/phi/...)
      │  → blocked: metadata only, never downloaded
      ▼
[Layer 3] Download file
      ▼
[Layer 4] Local Python regex scan (SSN, MRN, DOB, email, phone, FHIR, ICD-10...)
      │  → PHI found: quarantine (delete content, write notice)
      │  → Clean: proceed
      ▼
[Layer 5] Truncate large text files (size only, not PHI)
      ▼
[Layer 6] Write manifest with PHI Status column
      ▼
[Layer 7] Agent reads manifest → applies Step 2.5 pre-check
      ▼
[Layer 8] Agent reads/views clean files only
      ▼
[Layer 9] Judge agent checks output for PHI leakage
```

---

## Example

```
User: Respond to ticket PRODOPS-142

Agent:
1. Runs: python scripts/attachment_reader/fetch.py PRODOPS-142
   Output: "PHI Protection Summary: 5 total, 3 readable, 1 blocked (.csv), 1 quarantined (SSN detected)"
2. Reads: workspace/attachments/PRODOPS-142/_manifest.md
   Sees: airflow_error.log ✅ Clean, dag_screenshot.png ✅ Clean,
         patient_export.csv 🚫 BLOCKED, error_report.txt 🚨 QUARANTINED
3. Reads: workspace/attachments/PRODOPS-142/airflow_error.log  (clean)
4. Views: workspace/attachments/PRODOPS-142/dag_screenshot.png  (clean)
5. Notes in output:
   "⚠️ patient_export.csv was blocked (PHI-risk file type).
    ⚠️ error_report.txt was quarantined (SSN detected). Human review required."
6. Proceeds with validation → triage → remedy using full context
```

## Prerequisites

- `.env` file at repo root with `JIRA_BASE_URL` + auth credentials (see `.env.example`)
- Optional: `pip install PyMuPDF` for PDF processing
