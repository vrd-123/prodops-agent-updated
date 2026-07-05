---
description: "Full ticket analysis — validate, triage, search solutions, judge, and comment."
---

# /classify

Run the complete ProdOps workflow on a ticket.

## What it does
1. Fetches the ticket (Step 1: Ticket Intake)
2. Validates against SoP checklist (Step 2)
3. Classifies and routes (Step 3)
4. Searches for related issues and solutions (Step 4)
5. Judges output quality (Step 5)
6. Posts the full structured comment (Step 6)

## Usage
```
/classify PRODOPS-1234
```

## How to start
skill: `.cursor/skills/prodops-workflow-gate/SKILL.md` (runs all Steps 0–6)
