---
description: "Search for related past issues and documented solutions."
---

# /solution

Run solution search only.

## What it does
1. Fetches the ticket (Step 1: Ticket Intake)
2. Searches past Jira tickets, Confluence runbooks, and Slack threads
3. Returns related ticket links and documented solution steps
4. Posts solution recommendations as a comment

## Usage
```
/solution PRODOPS-1234
```

## How to start
skill: `.cursor/skills/prodops-workflow-gate/SKILL.md` (runs Steps 0–1, 4, 6 only)
