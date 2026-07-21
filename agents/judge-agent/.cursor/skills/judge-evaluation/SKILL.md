---
name: judge-evaluation
description: "Score the combined ProdOps bot output across 5 quality dimensions."
triggers:
  - judge
  - evaluate
  - score
---

# Judge Evaluation Workflow

> **Two scorecards.** Pick by intent (workflow-gate Step 0.5):
> - `ticket_op` → the ticket scorecard (Steps 1–9 below).
> - `knowledge_query` → the **Knowledge-Query scorecard** (see end of this file).
> Both use threshold 6.0 and the same retry/loop cap.

## Step 1 — Receive combined output
Accept the validation report + triage report + solution report from the main agent.

## Step 2 — Check correctness (30%)
- Are all Jira ticket keys real? (Don't verify via API — just check format and plausibility)
- Are Confluence URLs properly formatted?
- Are solution steps sourced?
- Deduct for: fabricated links, unsourced claims, contradictory statements.

## Step 3 — Check completeness (25%)
- All 3 sections present? (Validation, Triage, Solution)
- Validation has completeness score?
- Triage has classification + client + routing + priority?
- Solution has related tickets OR "nothing found" message?
- Deduct for: missing sections, incomplete fields.

## Step 4 — Check actionability (25%)
- Can the assignee act on the validation (knows what to fix)?
- Can the assignee act on the triage (knows who to contact)?
- Are solution steps specific enough to follow?
- Deduct for: vague steps, missing specifics, unclear ownership.

## Step 5 — Check relevance (10%)
- Are related past tickets actually about similar issues?
- Are Confluence pages relevant to this specific problem?
- Deduct for: unrelated tickets included, generic docs.

## Step 6 — Check format (10%)
- Does the output follow the structure from 020-response-format.mdc?
- Proper markdown formatting?
- Sections in correct order?

## Step 7 — Calculate total score
Weighted sum: (correctness × 0.3) + (completeness × 0.25) + (actionability × 0.25) + (relevance × 0.1) + (format × 0.1)

## Step 8 — Determine verdict
- Score >= 6.0 → PASS
- Score < 6.0 → FAIL (include specific improvement suggestions)

## Step 9 — Return scorecard
Return the JUDGE SCORECARD to the main agent. Do NOT post directly.

---

# Knowledge-Query Scorecard (intent = `knowledge_query`)

Use this instead of Steps 1–9 when evaluating a knowledge answer (no ticket).
Score each dimension 0–10, then take the weighted sum. Threshold 6.0 → PASS.

1. **Direct answer present (15%)** — Does it open with a one-line TL;DR that
   actually answers the exact question? Deduct heavily if the reader must infer it.
2. **Correctness & sourcing (25%)** — Is every fact first-hand and correctly stated?
   Deduct for fabricated URLs/keys, unsourced specifics (versions, dates, counts).
3. **Multi-source corroboration (15%)** — Are key facts backed by ≥ 2 independent
   sources? A single-source answer claiming "High" confidence is a deduct.
4. **Per-claim attribution (15%)** — Each claim cites its OWN source. One blanket
   citation for many facts → deduct.
5. **Confidence calibration (10%)** — Does the stated confidence match the evidence,
   and does it say what was / wasn't verified? Overconfidence (High on 1 source) → deduct.
6. **Conflict handling (5%)** — If sources disagree, is the conflict surfaced and
   resolved (prefer recent)? Silent cherry-picking → deduct.
7. **User actionability (10%)** — Does it end with a self-service lookup and/or a
   personalized next step so the user needs no follow-up?
8. **Format (5%)** — Follows the Knowledge-Answer format in `020-response-format.mdc`.

### Automatic conditions
- PHI/PII in the answer → score = 0, FAIL (same as ticket scorecard).
- An unsourced specific claim presented as fact (not marked `⚠️ unverified`)
  → cap Correctness at 4/10.
- "High" confidence with only one source → cap Confidence calibration at 3/10.

Return: Score (0–10), PASS/FAIL (threshold 6.0), improvement suggestions.
On FAIL → main agent re-runs K2 with feedback (max 2 retries).
