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

| Template             | Intent            | File                                     | Purpose |
|----------------------|-------------------|------------------------------------------|---------|
| `resolution_flow`    | `ticket_op`       | `templates/resolution_flow.html.j2`      | Symptom → Root Cause → Steps → Verify card for ticket-resolution replies. |
| `knowledge_answer`   | `knowledge_query` | `templates/knowledge_answer.html.j2`     | Text-shaped knowledge-query card: TL;DR → Key Facts → optional Stages → optional Matrix → Sources → Confidence → For you. Use for definitions, version mappings, ownership questions, comparisons. |
| `knowledge_workflow` | `knowledge_query` | `templates/knowledge_workflow.html.j2`   | Diagram-shaped knowledge-query card: TL;DR → **colored lanes with boxes-and-arrows, key/secret chips, per-lane tags** → optional side column (info boxes + legend) → Sources → Confidence → For you. Use for architecture / pipeline / workflow explanations ("explain how X works"). |

### Which knowledge_query template to pick

- **Diagram shape** ("explain the Seiji Deploy workflow", "walk me through the
  Airbyte sync pipeline", "how does AIR CD deploy?", "show me the SSH-tunnel
  data path") → `knowledge_workflow`.
- **Text shape** ("what DBR does AIR 3.x support?", "who owns the Airbyte
  config poller?", "which clients are offshore-accessible?") →
  `knowledge_answer`.

Both are **preferred over the Mermaid fallback** (Template 7 in
`templates/DIAGRAM_TEMPLATES.md`). See the decision rule in
`.cursor/rules/020-agent-behaviour/020-response-format.mdc`.

More layouts (timeline, comparison, service-map, triage-summary) can be
added by dropping new `<name>.html.j2` files here.

## `knowledge_answer` — block reference

Every block below is **optional** except `topic` and `tldr`. Drop any block
whose content cannot be sourced live (drop-if-unsourced, per
`.cursor/rules/000-global/000-guardrails.mdc`). Never invent URLs, page IDs,
dates, or Slack channels to fill a slot.

| Block         | Use for                                                | Notes |
|---------------|--------------------------------------------------------|-------|
| `topic`       | Card title                                             | Required. |
| `question`    | The user's original question                           | Rendered under the topic; helps verify the TL;DR actually answers it. |
| `kind`        | Free-text subtitle (`Version mapping`, `Workflow`, …)  | Cosmetic. |
| `tldr`        | One-line direct answer                                 | Required. Must actually answer `question`. |
| `facts`       | Bulleted key facts with per-claim source badges        | Each fact carries `sources: [{kind, label}]`. Use `warn: true` for `⚠️ unverified` items. |
| `stages`      | Numbered sequence (workflow / pipeline / release flow) | Each stage carries its own source badge. Use for "explain how X works" questions. |
| `matrix`      | Row-by-row comparison / mapping / version table        | Use for "what X does Y support", "who owns Z", etc. Each row cites a source. |
| `sources`     | Grouped source list (Confluence / Jira / Slack / Repo) | The complete first-hand reference set consulted for the answer. |
| `conflicts`   | Free-text conflict notes                               | Rendered as an amber callout inside Sources. Surface any disagreement between sources per `020-context-accuracy.mdc`. |
| `confidence`  | `{level, verified, not_verified}`                      | `level` is `High` / `Medium` / `Low`. High requires ≥ 2 independent first-hand sources (see `000-guardrails.mdc`). Always state both what was and wasn't verified. |
| `for_you`     | Self-service lookup + personalized recommendation      | Each item: `{kind: 'lookup' | 'recommend', text}`. This block closes the actionability requirement. |

### Source-badge kinds (`sources[].kind`)

`confluence` (default) · `jira` · `slack` · `repo` · `unverified` — controls
the badge color; keep the `label` short (≤ ~ 32 chars) so it doesn't wrap.

### Example commands

Text-shaped knowledge answer (version mapping):

```bash
.venv-render/bin/python -m scripts.diagram_render.render \
    --template knowledge_answer \
    --data    scripts/diagram_render/examples/knowledge_answer_air_dbr.json \
    --out     reports/samples/knowledge_answer_air_dbr.png
```

Diagram-shaped workflow explainer (Seiji-style, colored lanes + arrows):

```bash
.venv-render/bin/python -m scripts.diagram_render.render \
    --template knowledge_workflow \
    --data    scripts/diagram_render/examples/knowledge_workflow_seiji.json \
    --out     reports/samples/knowledge_workflow_seiji.png
```

## `knowledge_workflow` — block reference

Every block below is optional except `topic`, `tldr`, and `lanes`. Drop any
block whose content cannot be sourced live.

| Block         | Use for                                                | Notes |
|---------------|--------------------------------------------------------|-------|
| `topic`       | Card title                                             | Required. |
| `question`    | The user's original question                           | Rendered under the topic. |
| `kind`        | Free-text subtitle (`Workflow / architecture`, …)      | Cosmetic. |
| `tldr`        | One-line direct answer                                 | Required. |
| `lanes`       | Ordered list of subsystems / paths (colored rows)      | Required — the boxes-and-arrows body. Each lane has `title`, `color` (`blue` \| `green` \| `orange` \| `purple` \| `teal` \| `slate`), optional `direction` (`ltr` default \| `rtl`), `nodes[]`, optional `edges[]` (labels for the arrow between adjacent nodes), optional `tag_label` + `tags[]` for the footer row. |
| `lanes[].nodes[]` | Individual boxes                                   | Each node: `icon`, `title`, optional `sub`, optional `chips[]` (attached mini-boxes for keys, secret paths, tenant-config pointers). Chip `kind` accepts `key` (amber) or `pubkey` (purple). |
| `side`        | Right rail                                             | List of boxes; each is either `type: "info"` (title + items with icon/title/sub) or `type: "legend"` (title + items with icon/text). Omit `side` to use a single-column layout. |
| `sources`     | Grouped source list                                    | Same shape as `knowledge_answer`. |
| `confidence`  | `{level, verified, not_verified}`                      | Same as `knowledge_answer`. |
| `for_you`     | Self-service lookup + personalized recommendation      | Same as `knowledge_answer`. |

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
