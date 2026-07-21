# /generate-script

Generate a configured automation script for a PRODOPS ticket.

## Usage

```
/generate-script PRODOPS-3352
```

## What it does

1. Reads the PRODOPS ticket from Jira (read-only)
2. Detects the task type (S3 Copy or FHIR Cleanup)
3. Extracts parameters from ticket metadata + description
4. Resolves infrastructure context from env_config.yaml
5. Generates a complete, copy-paste-ready shell script
6. Posts the script to the Slack channel as a code block

## Supported task types

- **S3 Copy/Sync** — Break-glass pod + aws s3 sync/cp
- **FHIR Cleanup** — fhir_cleanup.py with dry-run → execute

## Prerequisites

Before running the generated script, the engineer must have:
- ✅ JIT access activated for the target tenant
- ✅ AWS CLI + kubectl installed
- ✅ For FHIR: fhir_cleanup.py + fhir_environments.yaml downloaded

## Important

- Jira is **read-only** — the bot never comments on tickets
- The bot **generates** scripts — it never **executes** them
- The dry-run step is always mandatory before execution
