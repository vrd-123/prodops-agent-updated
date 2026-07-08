"""
Attachment Reader for ProdOps Agent Pipeline (Cursor-native version)
====================================================================

Downloads Jira ticket attachments to a local workspace folder and
extracts text where possible. The Cursor agent then reads text files
and views images natively — no separate vision API needed.

Usage (from agent prompt or terminal):
    python scripts/attachment_reader/fetch.py PRODOPS-42

The script creates:
    workspace/attachments/PRODOPS-42/
        ├── _manifest.md          ← summary the agent reads first
        ├── error.log             ← text file (agent reads directly)
        ├── screenshot.png        ← image (agent views directly)
        └── report_extracted.txt  ← text pulled from report.pdf
"""

from .fetch import fetch_attachments

__all__ = ["fetch_attachments"]
