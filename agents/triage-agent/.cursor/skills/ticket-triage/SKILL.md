---
name: ticket-triage
description: "7-step triage workflow for ProdOps tickets."
triggers:
  - triage
  - classify
  - route
  - assign
---

# Ticket Triage Workflow

## Step 1 — Receive ticket context
Accept ticket context + triage routing config + matched service config from main agent.

## Step 2 — Classify ticket
Analyze title + description to classify:
- **customer_breakage**: Customer-facing impact (data not loading, reports broken, API errors for clients)
- **internal_breakage**: Internal systems/tooling issues (pipeline failures, infra problems, monitoring gaps)
- **enhancement**: Improvements, new capabilities, process changes
Provide reasoning for the classification.

## Step 3 — Identify client
Extract client name from: ticket labels, description, reporter email domain, component tags.
If no client identifiable → flag as "Unknown — manual review needed."

## Step 4 — Check client access
Load `config/triage-routing.yaml`:
- Check if client is in `onshore_only_clients` → Onshore-only
- Check if client is in `offshore_accessible_clients` → Offshore-accessible
- If client not listed → default to Onshore-only (safer default)

## Step 5 — Determine routing
- Onshore-only → assign to Stephen (or configured onshore default)
- Offshore-accessible → assign to Deepak (or configured offshore default)
- If special_rules matched (security, P0) → route per special rule overrides

## Step 6 — Validate priority
Compare ticket priority against SLA from matched service config. Flag mismatches.

## Step 7 — Return report
Return structured TRIAGE REPORT. Do NOT post directly.
