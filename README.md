# The Anakrisis Protocol

**Ethics-aware OSINT investigation planning and risk evaluation, delivered as an MCP server.**

Anakrisis is a [Model Context Protocol](https://modelcontextprotocol.io) server that brings structure, risk visibility, and documentation discipline to open-source intelligence work. It classifies investigations, scores risk against local YAML doctrine, flags prohibited actions, and scaffolds defensible case documentation — all before a single query leaves your machine.

It is a decision-support layer, not a collection engine. Anakrisis never touches the internet.

---

## What it is — and what it is not

| Anakrisis IS | Anakrisis is NOT |
|---|---|
| An investigation planning assistant | An OSINT data-collection tool |
| A risk classification engine (LOW / MEDIUM / HIGH) | A scraping or automation framework |
| A policy and doctrine interpretation layer | A verification or attribution service |
| A documentation and case-structure aid | A bypass, evasion, or anonymity tool |

The advisory model is deliberate: Anakrisis surfaces warnings, hard stops, and safer alternatives, but it does not halt execution. **Operational decisions — and responsibility for them — remain with the investigator.**

---

## Tools

Nine MCP tools cover the investigation lifecycle from intake to publication:

| Tool | Phase | Purpose |
|---|---|---|
| `MissionBrief` | Planning | Classify the investigation, assign a risk tier, list hard stops and safe first steps |
| `CourseCorrection` | Any | Phase-specific guidance and risk re-assessment as new artifacts emerge |
| `RulesOfEngagement` | Pre-action | Advisory interlock: flag ToS, privacy, legal, and operational risks; mark hard stops; suggest safer alternatives |
| `CreateCase` | Intake | Scaffold a structured case workspace on disk |
| `TextAnalyzer` | Analysis | Doctrine-guided triage of messages, posts, and other textual artifacts |
| `GraphBuilder` | Analysis | Doctrine-guided entity and relationship mapping from case notes |
| `AssignTools` | Collection planning | Recommend external OSINT tools from a local catalog |
| `ReportTemplate` | Reporting | Structured report templates with documentation reminders |
| `ReportRedaction` | Publication | Audience-aware redaction guidance with an auditable redaction log |

### MissionBrief

The primary entry point. Given a goal (plus optional context: existing artifacts, constraints, actor role, method class, jurisdiction), it classifies the investigation type, computes a LOW / MEDIUM / HIGH risk tier, lists triggered risk factors and doctrine-driven hard stops, and proposes safe first steps drawn from the matching playbook.

### CourseCorrection

Mid-investigation guidance for the five lifecycle phases — `intake`, `planning`, `discovery`, `validation`, `reporting`. Re-assesses risk from newly acquired artifacts and raises an escalation alert when personal identifiers enter the picture.

### RulesOfEngagement

Call before executing a potentially risky action. Evaluates the proposed action against the `action_rules:` block in `doctrine/disallowed_actions.yaml`, covering terms-of-service, privacy, legal, and operational exposure, and suggests safer alternatives. Rules marked `hard_stop` render as a prohibition that authorization cannot clear. A call that matches no rule is reported as **unassessed, not cleared** — the ruleset is finite, so silence is not approval. Advisory only: it flags, it does not block.

### CreateCase

Creates a case workspace under `~/anakrisis/cases/<case_name>/` with standard files (`objective.md`, `notes.md`, `report.md`, `graph.md`, `metadata.json`) and evidence subdirectories (`Sources`, `Screenshots`, `PDFs`, `Intelligence`, `OtherEvidence`). Case names are validated to prevent path traversal. Existing case content is never modified: re-running against an existing case is refused unless explicitly requested, and even then only missing files are filled in.

### TextAnalyzer

Doctrine-guided analysis of textual artifacts (emails, chat logs, posts). Surfaces high-value intelligence and pivotable artifacts, highlights PII, notes intent and tone, flags concerning content, and recommends passive pivots — analysis and triage only, no collection.

### GraphBuilder

Doctrine-guided relationship mapping from investigative notes. Identifies entities and relationship chains, assigns conservative confidence levels, separates facts from inferences, and produces investigator-friendly, Obsidian-compatible graph notes.

### AssignTools

Recommends external OSINT tools from the static catalog in `doctrine/assigntools.yaml`, scored by artifact type (username, email, phone, domain, company, and more) and keyword overlap. It recommends tools; it never runs them.

### ReportTemplate

Loads a report template for the investigation type and audience, prepends a metadata header, and reminds you to separate facts from inferences, document methodology and limitations, and record what was *not* found.

### ReportRedaction

Prepares reports for public release, client delivery, or controlled disclosure. Applies audience-specific redaction profiles, identifies PII / SPII / source-sensitive material, emits structured replacement tokens instead of silent deletions, and generates a redaction log with a residual re-identification risk assessment.

---

## Architecture

```
MCP client (desktop app, agent CLI, or any MCP-capable host)
        │  stdio (JSON-RPC / MCP)
        ▼
Anakrisis MCP server (anakrisis.py, FastMCP)
        │  deterministic classification + heuristic risk scoring
        ▼
Local YAML doctrine (doctrine/, playbooks/, report_templates/)
```

All decision logic is driven by local configuration. The server loads doctrine, evaluates the user-described intent against it, and returns structured guidance. There are no API keys, no network calls, and no telemetry.

**Quiet by default.** The advisory tools (`MissionBrief`, `CourseCorrection`, `RulesOfEngagement`) only surface warnings, hard stops, and approval checklists when the input actually trips a trigger — a substantive risk factor, a hard-stop rule from `doctrine/disallowed_actions.yaml`, or an `action_rules:` match against the proposed action. Routine planning calls return clean planning output without boilerplate warnings. This gates presentation only; risk scoring itself is unchanged.

**Quiet is not the same as clear.** Suppressing boilerplate must never read as approval. When `RulesOfEngagement` matches no rule, it says so — *unassessed, not cleared* — because the ruleset is finite and an unrecognized action has not been evaluated. Detection is keyword-based, so a deliberately euphemistic description can evade it. Treat a silent result as a prompt to restate the action plainly, not as a green light.

---

## Repository layout

```
anakrisis/
├── anakrisis.py            # MCP server (FastMCP, stdio transport)
├── anakrisis               # Optional terminal launcher (see below)
├── doctrine/               # All decision doctrine (YAML)
│   ├── risk_rules.yaml           # Risk factors, scoring, tier thresholds
│   ├── disallowed_actions.yaml   # Hard-stop rules
│   ├── jurisdiction_rules.yaml   # Jurisdiction risk modifiers
│   ├── actor_profiles.yaml       # Actor role definitions
│   ├── method_classes.yaml       # Method classification schema
│   ├── assigntools.yaml          # OSINT tool catalog
│   ├── text_analyzer.yaml        # Text analysis doctrine
│   ├── graph_builder.yaml        # Relationship-mapping doctrine
│   ├── report_redaction.yaml     # Redaction profiles and rules
│   └── output_policy.yaml        # Output formatting / brevity policy
├── playbooks/              # Investigation-type playbooks (YAML)
├── report_templates/       # Report templates (Markdown)
├── Dockerfile
├── .mcp.json               # Project-scoped MCP registration
└── requirements.txt
```

---

## Getting started

### Requirements

- Python 3.10+
- `pip install -r requirements.txt` (installs `mcp` and `pyyaml`)

### Run the server directly

```bash
python3 anakrisis.py
```

The server speaks MCP over stdio and waits for a client — running it standalone is only useful to confirm it starts cleanly (missing doctrine files are logged as warnings and fall back to built-in defaults).

### Register with an MCP client

The repository ships a project-scoped `.mcp.json`, so MCP clients that support project configuration (such as Claude Code) pick the server up automatically when launched from the repo root.

For other clients, or a global registration, point the client at the server with an absolute path:

```json
{
  "mcpServers": {
    "anakrisis": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/anakrisis/anakrisis.py"],
      "env": {}
    }
  }
}
```

### Docker

```bash
docker build -t anakrisis .
docker run -i --rm anakrisis
```

The image bundles the server, doctrine, playbooks, and report templates, and runs as a non-root user. Because MCP runs over stdio, keep `-i` in the run command (or configure your MCP client / gateway to launch the container). To persist case workspaces created by `CreateCase`, mount a volume over the container user's home:

```bash
docker run -i --rm -v ~/anakrisis:/home/mcpuser/anakrisis anakrisis
```

---

## Optional launcher

The `anakrisis` script in the repo root is a small terminal launcher (requires the `rich` package) for a Docker MCP Gateway + CLI workflow. It:

1. Verifies it is running from a project checkout
2. Checks that Docker is running, the `claude` CLI is on `PATH`, and the Docker MCP Gateway responds
3. Lists your most recent case workspaces from `~/anakrisis/cases`
4. Launches the MCP client CLI from the project root

```bash
./anakrisis
```

It is a convenience wrapper only — the server does not depend on it.

---

## Customizing doctrine

Every rule the server applies lives in a YAML file, not in Python. Risk factors and tier thresholds (`doctrine/risk_rules.yaml`), hard stops (`doctrine/disallowed_actions.yaml`), the tool catalog (`doctrine/assigntools.yaml`), analysis and redaction doctrine, playbooks, and report templates can all be edited — or replaced with your organization's own policy — without touching server code.

Doctrine files are cached with modification-time invalidation, so edits take effect on the next tool call without restarting the server.

---

## Design philosophy

Anakrisis follows the liability model of established security tooling:

- **Visibility over restriction** — risk exposure is surfaced, not suppressed
- **Warning over enforcement** — the system advises; it does not block
- **Structure over improvisation** — playbooks, phases, and templates keep work defensible
- **User responsibility over automated control** — judgment stays with the investigator

## Responsible use

Anakrisis produces advisory guidance only. It does not validate the legality of any action, does not constitute legal advice, and does not prevent misuse. Risk tiers and warnings are heuristic aids, not compliance determinations. You are solely responsible for ensuring your investigative activities comply with applicable laws, platform terms of service, and your organization's policies. Do not feed the system live personal data it does not need, and never treat its output as authorization to act.

## License

[MIT](LICENSE)
