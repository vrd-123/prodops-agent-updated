---
name: ticket-triage
description: "9-step multi-axis triage workflow for ProdOps tickets."
triggers:
  - triage
  - classify
  - route
  - assign
  - label
---

# Ticket Triage Workflow — Multi-Axis Classification

## Overview

This skill implements a 9-step triage workflow that classifies ProdOps
tickets on **three independent axes** simultaneously, matching how the
ProdOps board actually uses labels. It uses LLM semantic reasoning
guided by `config/triage-routing.yaml` — NOT pure keyword matching.

### Why multi-axis?

The ProdOps board has 20+ labels that operate on different dimensions:
- **Impact** (what kind of issue?) — exactly 1 label
- **Service/Client** (which service?) — 0 or more labels
- **Workflow** (what process state?) — 0 or more labels

39% of real tickets carry 2+ labels from different axes.
A flat A/B/C classification cannot capture this.

---

## Step 1 — Receive ticket context

Accept from the main agent:
- Ticket fields: key, summary, description, issue type, priority, existing labels, reporter, environment
- Full content of `config/triage-routing.yaml` (the taxonomy)
- Matched service config from `config/ticket-rules/_index.yaml` (if found)

Validate that ALL required inputs are present before proceeding.

---

## Step 2 — Impact Type Classification (exactly ONE)

Read the FULL ticket context — do not scan for keywords. Understand what
the ticket is actually about, then classify into exactly one:

| Impact Type | Key Question | Examples |
|-------------|--------------|----------|
| `customer_breakage` | Is a client seeing something broken? | "Users not able to access Power BI Dashboard", "FSI completes without loading data" |
| `internal_breakage` | Is an internal system broken, client NOT impacted yet? | "Copy data files from Prod to Dev", "Authentication Token Expiry in Stage Databricks" |
| `client_request` | Is a client requesting something (not reporting breakage)? | "Enable SFTP for tenant", "Clean up directories in S3" |
| `enhancement` | Is this improving something that already works? | "Air policy upgrade for workflows", "Add retry logic to data copier" |

### Decision rules for ambiguous cases

1. **Both customer + internal impact** → pick `customer_breakage` (higher severity).
   The internal aspect will be captured via service/workflow tags.

2. **Pipeline failure caused client-visible data issues** → `customer_breakage`,
   NOT `internal_breakage`. The pipeline-failure gets captured as a workflow tag.

3. **Data copy to fix a broken environment** → `internal_breakage` + `data_copier_yes`.
   Data copy for a client request → `client_request` + `data_copier_yes`.

4. **Keyword traps to avoid:**
   - "client S3 bucket" does NOT mean `customer_breakage`
   - "pipeline monitoring dashboard" may be `customer_breakage` if client-facing
   - "FHIR cleanup" is typically `internal_breakage`, but FHIR API errors
     visible to clients are `customer_breakage`

Provide a one-sentence reasoning.

---

## Step 3 — Service / Client Tag Assignment (zero or more)

For each `service_tag` defined in `config/triage-routing.yaml`, read its
`match_if` description and evaluate whether it applies to this ticket.

| Tag | Match When |
|-----|-----------|
| `data_copier_yes` | Copying data between environments, data sync jobs, S3 copies |
| `BlueKC` | Blue Cross Blue Shield Kansas City client/environment/data |
| `BCI` | Blue Cross Idaho client/environment/data |
| `gainwell` | Gainwell client, GW API, GW tenant, MDP |
| `GW-OR` | Gainwell Oregon specifically |
| `Manifest` | Manifest files, manifest generation/copying |
| `ngen` | ngen pipeline, next-gen infrastructure |
| `FHIR` | FHIR resources, FHIR store/API, HealthLake, FHIR cleanup |

### Rules
- Use `match_if` description as primary decision criteria — NOT just keywords.
- Apply ALL tags that are relevant. A ticket can have multiple service tags.
- Reference `co_occurrence_note` when available (e.g., `data_copier_yes`
  almost always co-occurs with `internal_breakage`).
- If keywords are present but the context doesn't match `match_if` → do NOT apply.

Provide a one-sentence reasoning per applied tag.

---

## Step 4 — Workflow / Dependency Tag Assignment (zero or more)

For each `workflow_tag` defined in `config/triage-routing.yaml`, evaluate
whether it applies.

| Tag | Match When |
|-----|-----------|
| `GWL-Dependency` | We are WAITING on Gainwell for something |
| `GWL-Blocker` | Gainwell is WAITING on us — their work is blocked |
| `GWL-0057` | Involves CMS-0057 compliance, interop, Onyx |
| `GWL-0057-IN` | Specifically INBOUND 0057 data ingestion |
| `SWAT-TODO` | Flagged for SWAT/on-call follow-up |
| `pipeline-failure` | An actual pipeline/DAG/workflow/ETL job has failed |
| `UAT` | Work is in UAT environment or for UAT validation |
| `Deliverable` | Tied to a formal deliverable/milestone |

### Key distinctions
- **GWL-Dependency vs GWL-Blocker**: Dependency = we wait on them.
  Blocker = they wait on us. Do not confuse these.
- **pipeline-failure**: Only if an actual job/workflow failed. General
  infra issues without a specific pipeline failure → do NOT apply.

Provide a one-sentence reasoning per applied tag.

---

## Step 5 — Combine All Labels

Merge the outputs from Steps 2-4 into a single label list:

```
All Labels = [impact_type] + [service_tags...] + [workflow_tags...]
```

Example: `[customer_breakage, BlueKC, FHIR, GWL-Dependency]`

This is the complete set of labels the ticket should carry.

---

## Step 6 — Identify client

Extract the client name from ticket context. Search in this order:
1. **Existing Jira labels** — most reliable
2. **Ticket title** — often contains client name or abbreviation
3. **Ticket description** — look for client names, environment names (e.g., "bcidaho-stg")
4. **Reporter email domain** — sometimes reveals the client
5. **Component tags** — if the project uses Jira components

Common ProdOps clients: Gainwell, BlueKC, BCI, BCBSMA, BCBSNC, BCBSM,
Cambia, Highmark, Inovalon, Cotiviti, MedStar, Clover.

If no client can be identified → set client to "Unknown".
Note where the client was identified from (for audit trail).

---

## Step 7 — Check client access + determine routing

Load `config/triage-routing.yaml` and check client access:

| Client list | Access level | Default handler |
|-------------|-------------|-----------------|
| `onshore_only_clients` | Onshore-only | Stephen |
| `offshore_accessible_clients` | Offshore-accessible | Deepak |
| Not listed | Onshore-only (safer default) | Stephen |

Check for overrides in `routing`:
- `security_override` → escalate to security team
- `p0_override` → escalate to SWAT on-call

---

## Step 8 — Validate priority

Compare the ticket's current Jira priority against:
1. The severity described in the ticket content
2. The SLA from the matched service config in `config/ticket-rules/_index.yaml`

Report alignment:
- ✅ **Matches** — priority is appropriate
- ⚠️ **Mismatch** — explain why (e.g., "P3 on a production outage affecting client data")

---

## Step 9 — Rate confidence + return report

Rate your confidence in the OVERALL classification (1-5).

| Score | Meaning | Action |
|-------|---------|--------|
| 5 | Crystal clear | Proceed |
| 4 | Very confident, minor ambiguity | Proceed |
| 3 | Reasonable, some uncertainty | Proceed, note uncertainty |
| 2 | Low confidence | Flag `needs_manual_review = true` |
| 1 | Guessing | Flag `needs_manual_review = true` |

Return the structured **TRIAGE REPORT** (format defined in `agent.md`).
Do NOT post it as a Jira comment — return it to the main agent only.

---

## Common multi-label patterns (reference)

These patterns are observed from real ProdOps ticket data. Use them as
guidance, but always verify against the actual ticket content.

| Pattern | When |
|---------|------|
| `internal_breakage` + `data_copier_yes` | Any data copy task between environments |
| `internal_breakage` + `FHIR` + `GWL-Dependency` | FHIR cleanup requests blocked on Gainwell |
| `customer_breakage` + `FHIR` + `[client]` | FHIR API errors visible to a client |
| `internal_breakage` + `BlueKC` | BlueKC FSI runs (unless failure impacts client) |
| `internal_breakage` + `GWL-0057` + `GWL-0057-IN` | 0057 inbound data ingestion failures |
| `customer_breakage` + `pipeline-failure` + `[client]` | Pipeline failure causing client data issues |
| `customer_breakage` + `GWL-Dependency` | Client issue waiting on Gainwell response |
| `client_request` + `[client]` | Client-initiated requests (SFTP, config, cleanup) |
| `enhancement` | Usually solo — internal improvements rarely have service/workflow tags |

---

## Anti-patterns (things to NEVER do)

| ❌ Anti-pattern | ✅ Correct approach |
|----------------|---------------------|
| Classify based on a single keyword | Read full ticket context + match_if descriptions |
| Default to `internal_breakage` when unsure | Use confidence score + flag for manual review |
| Assign only one label total | Assign one impact_type + all relevant service/workflow tags |
| Skip reasoning fields | Every classification needs a one-sentence justification |
| Guess the client | If unclear, say "Unknown" and flag for review |
| Apply `GWL-Dependency` and `GWL-Blocker` together | They are mutually exclusive — pick the correct direction |
| Post triage results as Jira comment | Return to main agent only — you are read-only |
