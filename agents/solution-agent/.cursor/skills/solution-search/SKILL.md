---
name: solution-search
description: "Search for related past issues and documented solutions."
triggers:
  - solution
  - related issues
  - past tickets
  - search
---

# Solution Search Workflow

## Step 1 — Receive context
Accept ticket context + matched service config + knowledge links from main agent.

## Step 2 — Search Jira
- Build JQL: `project = PRODOPS AND text ~ "{keywords}" AND created >= -180d ORDER BY created DESC`
- Also search by component if available.
- Max 5 searches. Return top 5 most relevant tickets.

## Step 3 — Search Confluence (knowledge links first)
- If matched service has `knowledge_links` → read those pages first (max 3).
- If more context needed → broader Confluence search using ticket keywords.
- Look for: runbooks, troubleshooting guides, resolution steps.

## Step 4 — Search Slack (if needed)
- If Jira + Confluence didn't yield enough → search Slack.
- Channels: #prodops, #transporters-oncall, #platform-oncall, #swat.
- Max 3 searches.

## Step 5 — Compile results
Apply the response rules from agent.md:
- **Ticket links only** — no detailed summaries
- **Solution steps with source** — only if documented somewhere
- **Root cause** — only if explicitly documented, never guessed
- **Nothing found** → clear "no related issues" message

## Step 6 — Return report
Return structured SOLUTION REPORT. Do NOT post directly.
