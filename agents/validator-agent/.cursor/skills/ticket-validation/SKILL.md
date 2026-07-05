---
name: ticket-validation
description: "6-step SoP validation workflow for ProdOps tickets."
triggers:
  - validate
  - validation
  - checklist
---

# Ticket Validation Workflow

## Step 1 — Receive ticket context
Accept the ticket context object from the main agent (key, summary, description, all fields).

## Step 2 — Load checklist
Load `config/validation-checklist.yaml` to get the list of mandatory fields with their criteria.

## Step 3 — Check each field
For each checklist item:
- **Present**: Field exists and meets the minimum criteria (e.g., summary > 10 chars).
- **Missing**: Field is empty, null, or not set.
- **Incomplete**: Field exists but doesn't meet criteria (e.g., environment says "prod" but no cluster/region).

## Step 4 — Score
Calculate completeness: (present + N/A) / total_fields.
Fields marked N/A for certain issue types don't count against the score.

## Step 5 — Determine verdict
- **COMPLETE**: All required fields present (score = 9/9 or all applicable fields met).
- **INCOMPLETE**: 1+ required fields missing. List what's missing.
- **CRITICAL**: Priority or environment missing for a P0/P1 ticket.

## Step 6 — Return report
Return the structured VALIDATION REPORT to the main agent. Do NOT post it directly.
