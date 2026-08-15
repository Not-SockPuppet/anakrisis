# Anakrisis

**Ethics-aware OSINT investigation planning and risk evaluation, delivered as an MCP server.**

[![CI](https://github.com/Not-SockPuppet/anakrisis/actions/workflows/ci.yml/badge.svg)](https://github.com/Not-SockPuppet/anakrisis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Anakrisis is a [Model Context Protocol](https://modelcontextprotocol.io) server for
open-source intelligence work. It classifies investigations, scores their risk against
local YAML doctrine, flags prohibited actions, and scaffolds case documentation. It
runs alongside a local or cloud AI agent, performs no collection itself, and makes no
network calls: all decision logic is deterministic Python evaluating local
configuration.

### Example client interaction

A user asks the assistant to look up a target's email addresses using an
un-attributed web persona. The assistant calls `MissionBrief` with the goal, the
starting artifact, and the stated constraint (`goal="Look up the target's email
addresses using an un-attributed web persona"`, `what_you_have="a username"`,
`constraints="passive only"`):

```text
📋 INVESTIGATION PLANNING ASSESSMENT

## Key Findings
- Classification: general_investigation
- Risk tier: TIER_MEDIUM
- Response mode: restricted
- Triggered risk factors: 2

## Risk Factors
- Total risk score: 6 (floor 0, cap 20)
- Insufficient planning context (+2): Key planning inputs are missing, reducing
  reliable risk assessment.
- No explicit authorization or consent stated (+4): The plan does not include a
  documented authorization basis (or indicates lack of authorization).

## Required Approvals
- Supervisor approval
```

If the persona then tries to make contact, `RulesOfEngagement` returns a hard stop:

```text
🛑 ACTION PROHIBITED

## Key Findings
- Safety level: 🛑 PROHIBITED - HARD STOP
- This action is disallowed by doctrine. Do not proceed. No authorization level
  clears a hard stop.

## Hard Stops
- Contacting or interacting with the target -- breaks passive-only scope and
  alerts them. Applies to research personas exactly as it does to a real account

## Safer Alternatives
- Do not initiate contact; route any approach through counsel of record
- Rely on content visible without interaction, and log the visibility state
```

The distinction is the action, not the account: a persona is permitted for passive
viewing, while any interaction with the target is a hard stop regardless of which
account performs it.

---

## What it is — and what it is not

| Anakrisis IS | Anakrisis is NOT |
|---|---|
| A governance layer for agent-driven collection | A verification or attribution service |
| A risk classification engine (LOW / MEDIUM / HIGH) | A bypass, evasion, or anonymity tool |
| A policy and doctrine interpretation layer | A scraper or automation framework in its own right |
| An investigation planning and documentation aid | A substitute for your own legal judgement |

The advisory model is deliberate: Anakrisis surfaces warnings, hard stops, and safer alternatives, but it does not halt execution. **Operational decisions — and responsibility for them — remain with the investigator.**

---

## Install

### Container image (no clone required)

Published images are available from the GitHub Container Registry:

```bash
docker pull ghcr.io/not-sockpuppet/anakrisis:latest
```

Register it with an MCP client by having the client launch the container. Because
MCP runs over stdio, `-i` is required:

```json
{
  "mcpServers": {
    "anakrisis": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "${HOME}/anakrisis:/home/mcpuser/anakrisis",
        "ghcr.io/not-sockpuppet/anakrisis:latest"
      ],
      "env": {}
    }
  }
}
```

The volume mount persists case workspaces created by `CreateCase`; omit it if you
do not need them to survive the container exiting.

### From source

**Requirements:** Python 3.10+

Clone the repository and install its dependencies:

```bash
git clone https://github.com/Not-SockPuppet/anakrisis.git
cd anakrisis
pip install -r requirements.txt
```

Alternatively, install it as a package. This pulls the dependencies and adds an
`anakrisis-server` command on your `PATH`:

```bash
pip install .
```

### Register with an MCP client

The repository ships a project-scoped `.mcp.json`, so clients that support project
configuration (such as Claude Code) pick the server up when launched from the repo
root. Because that config uses a relative path, it only works from the repository
directory.

For other clients, or a global registration, point the client at the server with an
absolute path:

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

If you installed the package with `pip install .`, use the console script instead of
a file path:

```json
{
  "mcpServers": {
    "anakrisis": {
      "type": "stdio",
      "command": "anakrisis-server",
      "env": {}
    }
  }
}
```

Restart the client and the nine tools appear.

<details>
<summary>Running it directly, and Docker</summary>

```bash
python3 anakrisis.py
```

The server speaks MCP over stdio and waits for a client — running it standalone is only useful to confirm it starts cleanly (missing doctrine files are logged as warnings and fall back to built-in defaults).

```bash
docker build -t anakrisis .
docker run -i --rm anakrisis
```

The image bundles the server, doctrine, playbooks, and report templates, and runs as a non-root user. Because MCP runs over stdio, keep `-i` in the run command (or configure your MCP client / gateway to launch the container). To persist case workspaces created by `CreateCase`, mount a volume over the container user's home:

```bash
docker run -i --rm -v ~/anakrisis:/home/mcpuser/anakrisis anakrisis
```

</details>

---

## Choose your model: cloud or local

Anakrisis is just an MCP server. It works with **any** MCP-capable assistant, and the choice of what drives it is genuinely yours — it changes the character of the tool rather than whether it functions.

| | Cloud — Claude, Gemini, GPT, any MCP-capable model | Local — Ollama, LM Studio, llama.cpp |
|---|---|---|
| **Reasoning** | Stronger. Better classification, sharper analysis, more useful pivots | Weaker, and more so on smaller models |
| **Speed** | Fast, no local hardware needed | Depends entirely on your machine |
| **Web access** | Usually built in — it can go and collect for you | None. You run the collection yourself |
| **Privacy** | Your case context goes to a provider's API | **Nothing leaves your machine** |

**The trade is privacy against reasoning and speed.** The right choice depends on the case: a public-record company check and an investigation involving a vulnerable person have different requirements.

Worth knowing either way: the doctrine, risk scoring, and hard stops are deterministic Python and YAML. They behave identically no matter what model you attach — a weaker local model doesn't get weaker guardrails, only weaker analysis.

### Cloud setup

Use the JSON above with any MCP-capable client — Claude Desktop, Claude Code, or anything else that speaks MCP.

### Local setup

Any MCP-capable local client works. With [Ollama](https://ollama.com) behind a client that supports MCP:

```bash
ollama pull llama3.1
```

Then register Anakrisis with your client exactly as in the JSON above — the server doesn't care what's on the other end.

For local models, prefer the larger instruct-tuned variants where your hardware allows. The nine tools return structured text that a model has to reason over, and very small models tend to summarise the guidance away rather than act on it.

### Clean Execution Hint

To keep output logs completely free of irrelevant tool alerts, specify your model environment explicitly in your client config's environment block:

```json
"env": {
  "ANAKRISIS_COLLECTION_MODE": "local"
}
```

Options: `cloud` | `local` | `auto` (default).

---

## On research personas

Anakrisis natively manages non-attributable research personas ("sock puppets") by separating **passive viewing** from **active interaction**.

| Action Type | Protocol Classification | System Action |
| :--- | :--- | :--- |
| **Passive Only** (Public profile/page viewing) | `passive_only` | ✅ Permitted & Encouraged |
| **Passive Plus** (Logged-in profile/story views) | `passive_plus` | ⚠️ Warns investigator of trace notifications |
| **Active Interaction** (Follow, DM, comment) | `hard_stop` | 🚫 Blocked by local doctrine rules |

Full reasoning, edge cases, and the rules behind it: [docs/research_personas.md](docs/research_personas.md).

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

The primary entry point. Given a goal (plus optional context: existing artifacts, constraints, actor role, method class, jurisdiction), it classifies the investigation type, computes a risk tier (`TIER_LOW` through `TIER_CRITICAL`), lists triggered risk factors and doctrine-driven hard stops, and proposes safe first steps drawn from the matching playbook.

### CourseCorrection

Mid-investigation guidance for the five lifecycle phases — `intake`, `planning`, `discovery`, `validation`, `reporting`. Re-assesses risk from newly acquired artifacts and raises an escalation alert when personal identifiers enter the picture.

### RulesOfEngagement

Call before executing a potentially risky action. Evaluates the proposed action against the `action_rules:` block in `doctrine/disallowed_actions.yaml`, covering terms-of-service, privacy, legal, and operational exposure, and suggests safer alternatives. Rules marked `hard_stop` render as a prohibition that authorization cannot clear. A call that matches no rule is reported as **unassessed, not cleared** — the ruleset is finite, so silence is not approval. Advisory only: it flags, it does not block.

### CreateCase

Creates a case workspace under `~/anakrisis/cases/<case_name>/` with standard files (`objective.md`, `notes.md`, `report.md`, `graph.md`, `metadata.json`) and evidence subdirectories (`Sources`, `Screenshots`, `PDFs`, `Intelligence`, `OtherEvidence`). Case names are validated to prevent path traversal. Existing case content is never modified: re-running against an existing case is refused unless explicitly requested, and even then only missing files are filled in.

### TextAnalyzer

Doctrine-guided analysis of textual artifacts (emails, chat logs, posts). Surfaces high-value intelligence and pivotable artifacts, highlights PII, notes intent and tone, flags concerning content, and recommends passive pivots. The tool works only on text you supply and performs no collection itself — acting on the pivots it suggests is the agent's job.

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

**Quiet by default.** The advisory tools (`MissionBrief`, `CourseCorrection`, `RulesOfEngagement`) surface warnings, hard stops, and approval checklists only when the input trips a trigger — a substantive risk factor, a hard-stop rule from `doctrine/disallowed_actions.yaml`, or an `action_rules:` match against the proposed action. Routine planning calls return planning output without warning sections. This gates presentation only; risk scoring itself is unchanged.

**A quiet result is not a clearance.** When `RulesOfEngagement` matches no rule, it reports the action as unassessed rather than cleared, because the ruleset is finite and an unrecognized action has not been evaluated. Detection is keyword-based, so a deliberately euphemistic description can evade it. A no-match result means the action should be restated plainly and re-checked, not that it is approved.

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
├── tests/                  # pytest suite (doctrine fixtures, matching, templates)
├── docs/
│   ├── tools.md                  # Full per-tool reference
│   ├── doctrine.md               # How each doctrine file is evaluated
│   └── research_personas.md      # Persona doctrine, reasoning and edge cases
├── Dockerfile
├── .mcp.json               # Project-scoped MCP registration
├── pyproject.toml          # Packaging, dependencies, tool config
└── requirements.txt
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

## Design approach

Anakrisis follows the liability model common to established security tooling:

- It surfaces risk exposure rather than suppressing it.
- It advises and warns; it does not block execution.
- It provides playbooks, phases, and templates to keep work documented.
- Responsibility for any action taken stays with the investigator.

## Responsible use

Anakrisis produces advisory guidance only. It does not validate the legality of any action, does not constitute legal advice, and does not prevent misuse. Risk tiers and warnings are heuristic aids, not compliance determinations. You are solely responsible for ensuring your investigative activities comply with applicable laws, platform terms of service, and your organization's policies. Do not feed the system live personal data it does not need, and never treat its output as authorization to act.

## Contributing and support

- **Contributing:** development setup and the test/lint workflow are in [CONTRIBUTING.md](CONTRIBUTING.md).
- **Security:** report vulnerabilities privately per [SECURITY.md](SECURITY.md).
- **Changes:** see [CHANGELOG.md](CHANGELOG.md). Releases follow [Semantic Versioning](https://semver.org).
- **Conduct:** participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE)
