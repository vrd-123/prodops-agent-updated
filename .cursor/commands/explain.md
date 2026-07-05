---
description: "Explain a ProdOps bot decision or the bot's analysis of a ticket."
---

# /explain

Explain why the bot made specific decisions about a ticket.

## What it does
1. Fetches the ticket and its bot comment history
2. Explains the reasoning behind:
   - Why a specific classification was chosen
   - Why a specific handler was assigned
   - Why certain past tickets were flagged as related
   - Why the priority/SLA was set

## Usage
```
/explain PRODOPS-1234
```

## How to start
skill: `.cursor/skills/knowledge-expansion/SKILL.md` (gathers context, then explains decisions)
