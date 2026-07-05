---
name: prodops-workflow-gate
description: "Master workflow gate — single source of truth for every ProdOps bot response."
triggers:
  - always
  - ticket
  - PRODOPS
  - validate
  - triage
  - solution
---

# ProdOps Workflow Gate — Master Workflow

Every response follows these steps **in order**. No step is ever skipped.

| Step | Name | When | Subagent |
|------|------|------|----------|
| 0 | Greeting | First message only | — |
| 1 | Ticket Intake | ALWAYS | — |
| 2 | Validation | ALWAYS | validator-agent |
| 3 | Triage | ALWAYS | triage-agent |
| 4 | Solution Search | ALWAYS | solution-agent |
| 5 | Judge | ALWAYS | judge-agent |
| 6 | Comment | ALWAYS | — |

---

## Step 0 — Greeting (first message only)
- Introduce yourself: "ProdOps Bot analyzing ticket [KEY]..."
- Skip on subsequent messages in the same conversation.

## Step 1 — Ticket Intake
1. Extract the JIRA ticket key from the user message or event trigger.
2. Fetch ticket fields: summary, description, issue type, priority, labels, components, reporter, assignee, environment, attachments.
3. Load `config/ticket-rules/_index.yaml` → match keywords against `tickets_registry`.
4. Check `special_rules` first (security_escalation, p0_fast_track, compliance_flag).
5. If match found → load the corresponding `prodops_*.yaml` (playbook, SLA, owning_team, knowledge_links).
6. If no match → load `config/knowledge_expansion.yaml` (global fallback).
7. Output: Parsed ticket object + matched service config (or fallback).

## Step 2 — Validation (consult validator-agent)
1. Build consultation prompt per `.cursor/skills/consultation-prompts/SKILL.md`.
2. Pass ticket fields + `config/validation-checklist.yaml` to validator-agent.
3. Validator checks each SoP field: present? complete? valid?
4. Receive structured checklist report with completeness score.
5. Output: Validation report (fields present, fields missing, score X/9).

## Step 3 — Triage (consult triage-agent)
1. Build consultation prompt for triage-agent.
2. Pass ticket fields + `config/triage-routing.yaml` + matched service config.
3. Triage-agent performs:
   a. **Classification**: customer_breakage / internal_breakage / enhancement
   b. **Client identification**: Extract client name from ticket
   c. **Access check**: Onshore-only or Offshore-accessible (per triage-routing.yaml)
   d. **Routing**: Determine handler (Stephen for onshore, Deepak for offshore)
   e. **Priority alignment**: Validate priority against SLA from service config
4. Output: Classification, client, access type, recommended assignee, priority + SLA.

## Step 4 — Solution Search (consult solution-agent)
1. Build consultation prompt for solution-agent.
2. Pass ticket summary + description + matched service keywords + knowledge_links.
3. Solution-agent performs:
   a. **Jira search**: Find related past PRODOPS tickets (JQL: similar keywords, same component, last 6 months)
   b. **Confluence search**: Check knowledge_links from service config, then broader Confluence search
   c. **Slack search**: Check relevant channels for discussions about this issue
4. **Response rules**:
   - Provide **related ticket links only** — no detailed summaries. Assignee reviews them.
   - If solution steps are documented (in past tickets or Confluence), provide them **with source attribution**.
   - If root cause is available from past data, include it. If not, do NOT guess.
   - If nothing found → "No related issues found. Assignee will investigate based on ticket priority."
5. Output: Related ticket links + solution steps (with sources) OR "nothing found" message.

## Step 5 — Judge (consult judge-agent)
1. Collect outputs from Steps 2, 3, 4.
2. Pass combined output to judge-agent.
3. Judge evaluates across 5 dimensions:
   - **Correctness** (30%): Are facts verifiable? Sources cited?
   - **Completeness** (25%): All sections present? No gaps?
   - **Actionability** (25%): Can the assignee act on this immediately?
   - **Relevance** (10%): Are related tickets actually related?
   - **Format** (10%): Does it follow the response format spec?
4. Judge returns: Score (0–10), PASS/FAIL, improvement suggestions.
5. If FAIL (score < 6.0) → re-run Step 4 with judge feedback. Max 2 retries.
6. If PASS → proceed to Step 6.

## Step 6 — Comment
1. Format the combined output using the response template from `020-response-format.mdc`.
2. Structure: Validation → Triage → Related Past Issues.
3. Post as a comment on the Jira ticket.
4. Done.
