# ProdOps Diagram Renderer

Renders HTML/CSS templates to PNG via Playwright + headless Chromium.
Produces **infographic-quality** diagrams (polished status cards, resolution
playbook cards, timelines) as an alternative to boxes-and-arrows Mermaid.

Use this pipeline when the Slack response benefits from a **branded,
information-dense summary card**. Use Mermaid for genuine flow diagrams
(architecture, sequence, lifecycle). See
`.cursor/rules/020-agent-behaviour/020-response-format.mdc` for the
decision rule.

## Install

```bash
python3 -m venv .venv-render
.venv-render/bin/pip install -r scripts/diagram_render/requirements.txt
.venv-render/bin/python -m playwright install chromium
```

## Render

CLI:

```bash
.venv-render/bin/python -m scripts.diagram_render.render \
    --template resolution_flow \
    --data    scripts/diagram_render/examples/resolution_flow_prodops_4567.json \
    --out     reports/samples/prodops_4567.png
```

Programmatic:

```python
from scripts.diagram_render.render import render
render(template="resolution_flow", data=payload, out_path="out.png")
```

## Templates

Each template is a Jinja2 file under `templates/`. The JSON schema is
"schema-by-example" — see the matching example in `examples/`.

| Template              | File                                       | Purpose |
|-----------------------|--------------------------------------------|---------|
| `resolution_flow`     | `templates/resolution_flow.html.j2`        | Symptom → Root Cause → Steps → Verify card for ticket-resolution replies |
| `knowledge_workflow`  | `templates/knowledge_workflow.html.j2`    | Lane-based workflow diagram for knowledge_query answers (architecture, pipelines, bot workflows) |

More layouts (timeline, comparison, service-map, triage-summary,
`knowledge_answer`) can be added by dropping new `<name>.html.j2` files here.

## Template contract

Every new template must:

1. Include a single `.page` root element (the renderer screenshots that
   element only — page background is ignored).
2. Use fixed viewport width (default 1200px); vertical size is auto.
3. Inline all CSS in a `<style>` block — no external CDN, no web fonts
   (fall back to system fonts) to keep rendering deterministic and
   offline-safe.
4. Use `|safe` explicitly on fields where inline HTML like `<b>` /
   `<code>` is expected. Autoescape is on by default.
5. Include a footer strip with `{{ generated_at }}` for auditability.

## Content requirements

Diagrams generated with this pipeline must satisfy the ProdOps
**Diagram Quality Rule** in
`.cursor/rules/020-agent-behaviour/020-response-format.mdc`:
real evidence quote, real source citation, real timestamp, no
fabricated data. If the ticket cannot supply the required inputs,
fall back to a smaller card or post text-only — never invent content.

## PHI / PII

Never render PHI/PII into the PNG. The renderer runs headless and
writes to disk under `reports/` (gitignored). Treat rendered PNGs
as ticket artifacts and follow the same handling rules as any log
excerpt: no raw patient identifiers, no SSN/MRN/DOB.

## Upload to Slack

```bash
curl -F "file=@reports/samples/prodops_4567.png" \
     -F "channels=$SLACK_CHANNEL_ID" \
     -F "thread_ts=$THREAD_TS" \
     -F "title=PRODOPS-4567 — Resolution Flow" \
     -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
     https://slack.com/api/files.uploadV2
```
