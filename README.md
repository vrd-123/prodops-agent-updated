# ProdOps Agent

The "brain" repository for the ProdOps Bot — an AI-powered ticket operations agent that validates, triages, and recommends solutions for PRODOPS Jira tickets.

## What This Repo Does

This repo contains **no application code**. It is a structured knowledge base that tells the Cursor AI agent how to behave. Think of it as the agent's brain: rules, workflows, skills, configs, and subagent definitions.

The bot reads a new ProdOps ticket → validates it against the SoP → classifies and routes it → searches for related past issues → posts a structured comment on the ticket.

## Architecture

```
Main Orchestrator (.cursor/agents/agent.md)
    │
    ├── Step 1: Ticket Intake (fetch + parse + keyword match)
    ├── Step 2: Validation ──→ validator-agent (SoP checklist)
    ├── Step 3: Triage ──────→ triage-agent (classify + route + assign)
    ├── Step 4: Solution ────→ solution-agent (search past issues)
    ├── Step 5: Judge ───────→ judge-agent (quality scorecard)
    └── Step 6: Comment (format + post to Jira ticket)
```

## Directory Structure

```
prodops-agent/
├── .cursor/
│   ├── agents/agent.md                          ← Main orchestrator
│   ├── commands/                                ← /validate, /triage, /solution, /classify, /explain
│   ├── rules/
│   │   ├── 000-global/                          ← No-skip, guardrails, API limits, read-only
│   │   ├── 010-org/                             ← Ticket registry, error recovery
│   │   └── 020-agent-behaviour/                 ← Skill triggers, orchestration, response format
│   └── skills/
│       ├── prodops-workflow-gate/               ← Master workflow (Steps 0-6)
│       ├── ticket-intake/                       ← Fetch + parse + keyword match
│       ├── knowledge-expansion/                 ← Confluence/Jira/Slack search
│       └── consultation-prompts/                ← Subagent prompt templates
├── agents/
│   ├── validator-agent/                         ← SoP checklist validation
│   ├── triage-agent/                            ← Classification + routing
│   ├── solution-agent/                          ← Past issue search
│   └── judge-agent/                             ← Quality scoring
├── config/
│   ├── validation-checklist.yaml                ← SoP field requirements
│   ├── triage-routing.yaml                      ← Client routing + assignment
│   ├── knowledge_expansion.yaml                 ← Global fallback knowledge
│   └── ticket-rules/
│       ├── _index.yaml                          ← Master registry (16 services)
│       └── prodops_*.yaml                       ← Per-service configs
└── .gitignore
```

## Key Differences from Transporters Agent

| Aspect | Transporters Agent | ProdOps Agent |
|--------|-------------------|---------------|
| Purpose | Code changes + engineering | Ticket analysis + comments |
| Output | Code, PRs, branches | Jira ticket comments only |
| Workflow | 10 steps (incl. code) | 6 steps (no code) |
| Subagents | DSP, QA, Security | Validator, Triage, Solution, Judge |
| Commands | 15 (incl. PR, deploy) | 5 (validate, triage, solution, classify, explain) |

## Guardrails

- **Never skip workflow steps** — even for small tasks
- **API rate limits** — Confluence: 3/turn, Jira: 5/turn, Slack: 3/turn
- **No hallucination** — every fact must have a source
- **PHI/PII protection** — never include patient data in comments
- **Read-only subagents** — only main agent posts comments
