---
name: judge-evaluation
description: "Score the combined ProdOps bot output across 5 quality dimensions."
triggers:
  - judge
  - evaluate
  - score
---

# Judge Evaluation Workflow

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
