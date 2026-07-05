---
name: ticket-intake
description: "Fetch and parse a JIRA ticket, resolve its service type via keyword matching."
triggers:
  - PRODOPS-
  - ticket
  - new ticket
  - intake
---

# Ticket Intake

## Purpose
Fetch a JIRA ticket, extract all relevant fields, and resolve which service it belongs to using `config/ticket-rules/_index.yaml`.

## Steps

### Step 1 — Fetch ticket
- Extract ticket key from user message (e.g., PRODOPS-1234).
- Fetch via Jira API: summary, description, issue type, priority, labels, components, reporter, assignee, environment, created date, attachments, comments.

### Step 2 — Check special rules
- Load `config/ticket-rules/_index.yaml` → `special_rules`.
- Check ticket against `security_escalation.trigger_keywords` → if match: flag IMMEDIATE_ESCALATE.
- Check against `p0_fast_track.trigger_keywords` → if match: flag FAST_TRACK.
- Check against `compliance_flag.trigger_keywords` → if match: add compliance-review label.

### Step 3 — Resolve service type
- Load `tickets_registry` from `_index.yaml`.
- Match ticket title + description + labels against each entry's `keywords` array.
- **Priority resolution** (from `priority_resolution` config):
  1. `explicit_ticket_type` — Jira priority/type already set
  2. `label_based` — Labels match a known type
  3. `keyword_based` — Content keyword matching
- If match → load corresponding `prodops_*.yaml`.
- If no match → load `config/knowledge_expansion.yaml` (fallback).

### Step 4 — Build ticket context object
Assemble:
```yaml
ticket:
  key: PRODOPS-1234
  summary: "..."
  description: "..."
  issue_type: Bug
  priority: P1
  labels: [airbyte, CDC]
  components: [Airbyte]
  reporter: "user@abacusinsights.com"
  assignee: null
  environment: "production"
  created: "2026-07-05"
matched_service:
  type: airbyte
  config_file: prodops_airbyte.yaml
  owning_team: Transporters
  sla: {P1: {response: 1h, resolution: 8h}}
  playbook: [...]
  knowledge_links: [...]
special_flags: []
```

### Step 5 — Pass to workflow
Return the ticket context object to the prodops-workflow-gate for Steps 2–6.
