---
description: "Validate a ProdOps ticket against the SoP checklist."
---

# /validate

Run ticket validation only.

## What it does
1. Fetches the ticket (Step 1: Ticket Intake)
2. Runs the SoP validation checklist (Step 2: Validation)
3. Posts the validation results as a comment

## Usage
```
/validate PRODOPS-1234
```

## How to start
skill: `.cursor/skills/prodops-workflow-gate/SKILL.md` (runs Steps 0–2, 6 only)
