---
description: "Triage a ProdOps ticket — classify, route, and assign."
---

# /triage

Run ticket triage only.

## What it does
1. Fetches the ticket (Step 1: Ticket Intake)
2. Classifies the ticket (customer_breakage / internal_breakage / enhancement)
3. Identifies client and access type (onshore/offshore)
4. Recommends handler assignment
5. Posts triage results as a comment

## Usage
```
/triage PRODOPS-1234
```

## How to start
skill: `.cursor/skills/prodops-workflow-gate/SKILL.md` (runs Steps 0–3, 6 only)
