---
name: knowledge-expansion
description: "Gather deeper context from Confluence, Jira, and Slack when base knowledge is insufficient."
triggers:
  - knowledge
  - search confluence
  - find related
  - need more context
---

# Knowledge Expansion

## Purpose
When the solution-agent or main agent needs deeper context than what the ticket-rules YAML provides, this skill searches Confluence, Jira, and Slack for additional information.

## Protocol

### Step 1 — Assess what's available
- Check if `matched_service.knowledge_links` has been loaded.
- Check if those links were already read in this turn.
- If knowledge_links are sufficient → skip expansion.

### Step 2 — Load service-specific knowledge expansion
- If a service was matched, check `config/knowledge_expansion/knowledge_expansion_{service}.yaml`.
- Load relevant sections (troubleshooting, architecture, operations) — max 3 pages per turn.

### Step 3 — Confluence search (with limits)
- Search Confluence using ticket keywords. Prefer `Abacus NextGen 2.0` space.
- **Rate limit**: Max 3 page reads per turn.
- Read page summaries first; only read full content if summary is relevant.

### Step 4 — Jira historical search
- Search past PRODOPS tickets using JQL:
  - `project = PRODOPS AND text ~ "{keywords}" AND created >= -180d ORDER BY created DESC`
- **Rate limit**: Max 5 searches per turn.
- Return ticket keys and summaries for the solution-agent.

### Step 5 — Slack search (optional)
- If Jira/Confluence didn't yield enough, search Slack channels.
- Prefer: #prodops, #transporters-oncall, #platform-oncall, #swat.
- **Rate limit**: Max 3 searches per turn.

### Step 6 — Summarize with citations
- Compile all findings into a structured summary.
- Every fact must have a source citation.
- Return to the requesting agent/skill.

## Guardrail
- If all rate limits are hit and more context is needed → pause and tell the user:
  "I've reached the search limit for this turn. Would you like me to continue searching?"
