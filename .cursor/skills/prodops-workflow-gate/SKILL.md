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

Every response follows these steps **in order**. No step is ever skipped **for
its intent** (see Step 0.5 — the two intents run different step sets, but within
an intent nothing is skipped).

### Intent: `ticket_op` (a Jira ticket to validate/triage/solve)
| Step | Name | When | Subagent |
|------|------|------|----------|
| 0 | Greeting | First message only | — |
| 0.5 | Intent Detection | ALWAYS | — |
| 1 | Ticket Intake | ALWAYS | — |
| 2 | Validation | ALWAYS | validator-agent |
| 3 | Triage | ALWAYS | triage-agent |
| 4 | Solution Search | ALWAYS | solution-agent |
| 5 | Judge | ALWAYS | judge-agent |
| 6 | Comment | ALWAYS | — |

### Intent: `knowledge_query` (a general question, no ticket to action)
| Step | Name | When | Subagent |
|------|------|------|----------|
| 0 | Greeting | First message only | — |
| 0.5 | Intent Detection | ALWAYS | — |
| K1 | Query Intake | ALWAYS | — |
| K2 | Knowledge Search | ALWAYS | skill: knowledge-expansion (+ solution-agent) |
| K3 | Judge | ALWAYS | judge-agent (knowledge_query scorecard) |
| K4 | Answer | ALWAYS | — |

> Validation (Step 2) and Triage (Step 3) are **N/A** for `knowledge_query` —
> there is no ticket to validate or route. This is the ONLY sanctioned skip and
> it is intent-driven, not a shortcut. See `000-no-skipping-steps.mdc`.

---

## Step 0 — Greeting (first message only)
- Introduce yourself: "ProdOps Bot analyzing ticket [KEY]..." (ticket_op) or
  "ProdOps Bot — answering: [topic]..." (knowledge_query).
- Skip on subsequent messages in the same conversation.

## Step 0.5 — Intent Detection & Routing (ALWAYS)
Classify the incoming request into exactly ONE intent before doing anything else:

| Intent | Trigger signals | Path |
|--------|-----------------|------|
| `ticket_op` | A Jira key is present (e.g. `PRODOPS-1234`); a new-ticket event; user says "validate / triage / this ticket" | Steps 1 → 6 |
| `knowledge_query` | No ticket key; a general question ("what/which/how/does/when…"); asks for a fact, mapping, definition, or comparison | Steps K1 → K4 |

Rules:
- If a Jira key is present anywhere → default to `ticket_op` (even if phrased as a question about the ticket).
- If genuinely ambiguous (a question that might need a ticket) → ask one clarifying
  question OR proceed as `knowledge_query` and note the assumption.
- State the detected intent in one line before proceeding (internal reasoning, not the final answer body).

## Step 1 — Ticket Intake
1. Extract the JIRA ticket key from the user message or event trigger.
2. Fetch ticket fields: summary, description, issue type, priority, labels, components, reporter, assignee, environment, attachments.
3. **Attachment intake (MANDATORY, orchestrator-only).** If the ticket has any
   attachment listed in the Jira response, the **main orchestrator** — not a
   subagent — MUST run the attachment pipeline itself, from the repo root, in
   its own shell (this is the only environment guaranteed to have `.env` loaded):
   ```
   python scripts/attachment_reader/fetch.py {ISSUE_KEY}
   ```
   Then read `workspace/attachments/{ISSUE_KEY}/_manifest.md` and apply the
   PHI pre-check in `.cursor/skills/attachment-reader/SKILL.md` Step 2.5.
   - If `fetch.py` fails (e.g. `JIRA_BASE_URL not set`, HTTP 401/403, network
     error) → surface the exact error, do NOT silently degrade to metadata-only
     inference, and do NOT delegate the fetch to a subagent.
   - Subagents (validator/triage/solution/judge) MUST NOT run `fetch.py`
     themselves; they consume the manifest + clean file observations passed to
     them by the orchestrator (see `consultation-prompts` SKILL).
4. Load `config/ticket-rules/_index.yaml` → match keywords against `tickets_registry`.
5. Check `special_rules` first (security_escalation, p0_fast_track, compliance_flag).
6. If match found → load the corresponding `prodops_*.yaml` (playbook, SLA, owning_team, knowledge_links).
7. If no match → load `config/knowledge_expansion.yaml` (global fallback).
8. Output: Parsed ticket object + matched service config (or fallback) + attachment manifest path + clean-attachment observations (if any).

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

---

# Knowledge-Query Flow (intent = `knowledge_query`)

Use this path when Step 0.5 detects a general question with no ticket to action
(e.g. "what version of DBR do we support with AIR?"). Skip Validation and Triage —
they do not apply. **Never** answer from model knowledge alone (see
`000-context-accuracy.mdc` order and `000-guardrails.mdc` no-hallucination policy).

## Step K1 — Query Intake
1. Extract the topic, the exact question, and any entities (service, version, client, environment).
2. Check `config/knowledge-faq.yaml` for a canonical answer to this recurring question.
   - If a FAQ entry matches → use it as the seed answer, but STILL re-verify against
     its cited live sources in K2 (a cached answer is never posted unverified).
3. Resolve service context: run keyword matching against `config/ticket-rules/_index.yaml`
   and load the matched `prodops_*.yaml` `knowledge_links` if any; else
   `config/knowledge_expansion.yaml`.
4. Output: parsed question + entities + seed answer (if any) + knowledge_links to search.

## Step K2 — Knowledge Search (skill: knowledge-expansion, + solution-agent)
1. Run the full `knowledge-expansion` protocol — do NOT stop at the first hit.
   Exhaust the ladder within rate limits: Confluence → Jira history → Slack.
2. **Multi-source gate**: seek ≥ 2 independent sources before assigning High confidence.
   One source → cap confidence at Medium (see `000-guardrails.mdc`).
3. Capture, per fact: the claim + its source (URL / ticket key / Slack permalink) + date.
4. **Conflict handling**: if sources disagree, keep both, flag the conflict, and prefer
   the more recent per `000-context-accuracy.mdc`.
5. Output: fact list with per-claim sources, plus any conflicts and gaps.

## Step K3 — Judge (consult judge-agent — `knowledge_query` scorecard)
1. Pass the drafted answer + fact list to judge-agent using the `knowledge_query` scorecard.
2. Judge scores: direct-answer-present, correctness/sourcing, multi-source corroboration,
   per-claim attribution, confidence calibration, conflict-flagging, user-actionability, format.
3. If FAIL (< 6.0) → re-run K2 with judge feedback. Max 2 retries, then answer with a
   low-confidence disclaimer.

## Step K4 — Answer
1. Format using the **Knowledge-Answer format** in `020-response-format.mdc`.
2. Required elements: TL;DR direct answer first → body → per-claim Sources →
   calibrated Confidence (with what was/wasn't verified) → "For you (next steps)".
3. Deliver to the user (this intent posts an answer, not a Jira comment).
