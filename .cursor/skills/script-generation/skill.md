# Skill: Script Generation (Phase 2)

## Purpose

Generate configured, copy-paste-ready automation scripts from PRODOPS ticket metadata.
The engineer reviews and executes the script manually — the bot NEVER executes commands.

## Trigger

Activate this skill when the user message matches any of:
- `generate script for PRODOPS-XXXX`
- `script for PRODOPS-XXXX`
- `script PRODOPS-XXXX`
- `generate PRODOPS-XXXX`

Regex: `(?:generate\s+(?:script\s+(?:for\s+)?)?|script\s+(?:for\s+)?)?(PRODOPS-\d+)`

## Supported Task Types

| Type | Detection Signal | Script Output |
|------|-----------------|---------------|
| **S3 Copy/Sync** | Components="Data Copying" OR summary contains "copy" + s3:// URIs in description | Break-glass pod + `aws s3 sync/cp` |
| **FHIR Cleanup** | Components="FHIR Server" OR summary contains "FHIR Cleanup" + gw{nn}-{state}-{env} in description | `fhir_cleanup.py --dry-run` → `--execute` |

## Workflow

```
1. Extract ticket key from user message
2. Read PRODOPS ticket via Jira MCP (READ-ONLY — no comments, no updates)
3. Run ticket_parser.py logic:
   a. Detect task type (customfield_10370 → summary fallback → description fallback)
   b. Extract customer from customfield_10081 (list of dicts: [{"value": "BCI"}])
   c. Extract parameters from description:
      - S3 Copy: regex s3://abacus-[...] for URIs, classify source vs dest
      - FHIR: regex gw{nn}-{state}-{env} for FHIR env names, resource types, metadata tables
4. Resolve AWS profile + EKS cluster from phase2/config/env_config.yaml
5. Run script_generator.py logic:
   - S3 Copy → break-glass pod commands with dry-run + execute + validation
   - FHIR → fhir_cleanup.py commands with dry-run + execute + Databricks SQL
6. Post the complete script as a ```bash code block in the Slack thread
7. Add a one-line summary header above the script:
   "📋 PRODOPS-XXXX | S3 Copy | BCI Prod → Dev | Symplr"
```

## Critical Rules

- **Jira is READ-ONLY** — NEVER post comments or update ticket fields
- **Bot generates, human executes** — NEVER run the generated commands
- **Dry-run is always first** — Execute step is always commented out or comes after mandatory dry-run
- **Warnings are surfaced** — Path/bucket mismatches, multi-env vs workspace field disagreement
- **S3 URIs come from the ticket** — NEVER construct bucket names or account IDs
- **FHIR env names come from the ticket** — NEVER guess the environment

## File References

- `phase2/config/env_config.yaml` — Customer → AWS profile + EKS cluster mapping
- `phase2/parsers/ticket_parser.py` — Parameter extraction logic
- `phase2/generators/script_generator.py` — Script template generation

## Edge Cases

| Scenario | Handling |
|----------|----------|
| `customfield_10370` is null | Fall back to summary keywords, then description content |
| Workspace field says "Dev" but description has Dev + Stg | Trust description, flag warning |
| Metadata tables have full catalog path | Extract catalog directly from path |
| Metadata tables have NO catalog path | Infer: gw03-vt-dev → gw03_vtdev_catalog |
| Multi-env ticket (gw01-wv-dev, gw01-wv-stg) | Generate separate script blocks per environment |
| "Insurance Plan" (with space) | Normalize to "InsurancePlan" |
| No S3 URIs and no FHIR patterns | Return UNKNOWN with guidance on what fields to add |
| Path/bucket mismatch (dev bucket, stg folder) | Surface ⚠️ warning above script |
