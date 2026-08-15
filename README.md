# Anakrisis

**Ethics-aware OSINT investigation planning, collection, and risk evaluation, delivered as an MCP server.**

[![CI](https://github.com/Not-SockPuppet/anakrisis/actions/workflows/ci.yml/badge.svg)](https://github.com/Not-SockPuppet/anakrisis/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Anakrisis is a [Model Context Protocol](https://modelcontextprotocol.io) server for
open-source intelligence work. It plans investigations, classifies them, scores their
risk against local YAML doctrine, flags prohibited actions, and scaffolds case
documentation — and, driven by a cloud model, it goes and carries out the collection
too, like any web-enabled AI agent.

**Collection depends on which model drives it.** The server itself makes no network
calls; its decision logic is deterministic Python over local configuration. The
collection is performed by the model you connect:

- **Cloud model** (Claude, Gemini, GPT, …) has internet access, so it can run the
  searches and lookups Anakrisis recommends.
- **Local model** (Ollama, LM Studio, …) runs entirely on your machine with no web
  access, so it plans the collection and you carry it out.

It runs in any MCP-compatible client — the Claude desktop app, Claude Code, Cursor,
LM Studio, and others. Installing takes two steps and no coding; see
[Install](#install).

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

`MissionBrief` is the planning entry point and one of nine tools. The full set —
including `RulesOfEngagement`, which flags hard stops before a risky action, and the
analysis and reporting tools — is listed under [Tools](#tools).

---

## What it is — and what it is not

| Anakrisis IS | Anakrisis is NOT |
|---|---|
| A governance layer for agent-driven collection | A verification or attribution service |
| A risk classification engine (LOW → CRITICAL) | A bypass, evasion, or anonymity tool |
| A policy and doctrine interpretation layer | A scraper or automation framework in its own right |
| An investigation planning and documentation aid | A substitute for your own legal judgement |

The advisory model is deliberate: Anakrisis surfaces warnings, hard stops, and safer alternatives, but it does not halt execution. **Operational decisions — and responsibility for them — remain with the investigator.**

---

## Install

Anakrisis works with **any MCP-compatible client** — the Claude desktop and web apps,
Claude Code, Cursor, LM Studio, or anything else that speaks MCP. You do not need
Claude Code, and you do not need to write any code.

There are two steps: install Docker, then paste one config block into your client.

### Step 1 — Install Docker

Docker runs the server in a self-contained box, so you do not need Python or any
other dependency on your machine.

1. Download [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS,
   Windows) or install the Docker Engine on Linux.
2. Install it like any other application, then **launch it** and leave it running.

That is the only software you need. You do not have to download Anakrisis itself —
the image is fetched automatically the first time your client starts the server.

### Step 2 — Add Anakrisis to your client

Pick the section matching the app you use. Every one of them uses the same config; only
the place you put it differs.

<details open>
<summary><b>Claude desktop app</b> (Claude Sonnet / Opus — the regular Claude app)</summary>

1. Open Claude and go to **Settings → Developer → Edit Config**. This opens
   `claude_desktop_config.json` in a text editor.
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
2. Paste this in. If the file already has an `"mcpServers"` section, add the
   `"anakrisis"` block inside it rather than replacing the file:

   ```json
   {
     "mcpServers": {
       "anakrisis": {
         "command": "docker",
         "args": [
           "run", "-i", "--rm",
           "ghcr.io/not-sockpuppet/anakrisis:latest"
         ],
         "env": { "ANAKRISIS_COLLECTION_MODE": "cloud" }
       }
     }
   }
   ```

3. Save the file and **fully quit and reopen Claude** (not just close the window).
4. The nine tools appear. Because Claude has web access, it will offer to run the
   collection steps Anakrisis recommends.

</details>

<details>
<summary><b>Claude Code</b> (terminal)</summary>

One command — it writes the configuration for you:

```bash
claude mcp add anakrisis -e ANAKRISIS_COLLECTION_MODE=cloud -- docker run -i --rm -v "$HOME/anakrisis:/home/mcpuser/anakrisis" ghcr.io/not-sockpuppet/anakrisis:latest
```

Restart Claude Code and the nine tools appear. To remove it later:

```bash
claude mcp remove anakrisis
```

</details>

<details>
<summary><b>Cursor, Windsurf, and other MCP clients</b></summary>

These read the same JSON, usually from a file named `mcp.json` (Cursor:
**Settings → MCP → Add new global MCP server**). Use the same block as the Claude
desktop app above, then restart the client.

</details>

<details>
<summary><b>Local models (Ollama, LM Studio) — private, but you collect</b></summary>

A model running on your own machine has no internet access, so Anakrisis plans the
collection and hands the steps to you. Everything stays on your computer.

1. If you use Ollama, pull a model first. Prefer a larger instruct-tuned one — very
   small models tend to summarise the guidance away rather than act on it:

   ```bash
   ollama pull llama3.1
   ```

2. In your client's MCP configuration, use the same block as above but set the mode to
   `local`:

   ```json
   {
     "mcpServers": {
       "anakrisis": {
         "command": "docker",
         "args": [
           "run", "-i", "--rm",
           "ghcr.io/not-sockpuppet/anakrisis:latest"
         ],
         "env": { "ANAKRISIS_COLLECTION_MODE": "local" }
       }
     }
   }
   ```

3. Restart the client.

</details>

### Step 3 — Check it worked

Ask your assistant:

> Use MissionBrief to plan a background check on a vendor company. I have the company
> name and website, and I am authorized by procurement.

You should get an "Investigation Planning Assessment" back with a classification and
safe first steps. If nothing happens, see [Troubleshooting](#troubleshooting).

### Optional — keep case files on your computer

By default, case workspaces created by `CreateCase` live inside the container and
disappear when it exits. To keep them, add a volume mount using the **full path** to a
folder on your machine — configuration files cannot expand `~` or `$HOME`, so it must
be written out in full (for example `/Users/yourname/anakrisis` on macOS,
`/home/yourname/anakrisis` on Linux, or `C:\\Users\\yourname\\anakrisis` on Windows):

```json
"args": [
  "run", "-i", "--rm",
  "-v", "/Users/yourname/anakrisis:/home/mcpuser/anakrisis",
  "ghcr.io/not-sockpuppet/anakrisis:latest"
]
```

### Which model should you use?

| | Cloud model (Claude, Gemini, GPT, …) | Local model (Ollama, LM Studio, …) |
|---|---|---|
| **Collection** | The assistant runs it for you (has web access) | You run it yourself (no web access) |
| **Reasoning** | Stronger classification, analysis, and pivots | Weaker, more so on smaller models |
| **Speed** | Fast, no local hardware needed | Depends on your machine |
| **Privacy** | Case context goes to a provider's API | **Nothing leaves your machine** |

`ANAKRISIS_COLLECTION_MODE` accepts `cloud`, `local`, or `auto` (the default, which
guesses from the client name). Setting it explicitly keeps the collection offers
correct.

The doctrine, risk scoring, and hard stops are identical either way — they are
deterministic Python and YAML, so a weaker local model gets the same guardrails, only
weaker analysis.

### Troubleshooting

| Symptom | Fix |
|---|---|
| Tools do not appear | Fully quit and reopen the client — most only read the config at startup. |
| "docker: command not found" | Docker is not installed or not on `PATH`. Install Docker Desktop and launch it. |
| "Cannot connect to the Docker daemon" | Docker is installed but not running. Open Docker Desktop and wait for it to report Running. |
| "invalid reference format" or a literal `${HOME}` folder appears | A `-v` path is not a full path. Configuration files do not expand `~` or `$HOME`; write the path out in full. |
| First start is slow | The image is downloading (about 150 MB). Later starts are immediate. |
| Nothing works and you want a clean check | Run `docker run -i --rm ghcr.io/not-sockpuppet/anakrisis:latest` in a terminal. It should wait silently for input — that means the server starts correctly. Press Ctrl-C to exit. |

<details>
<summary>Run from source instead of Docker</summary>

**Requirements:** Python 3.10+

```bash
git clone https://github.com/Not-SockPuppet/anakrisis.git
cd anakrisis
pip install -r requirements.txt
```

Then point your client at the server with an absolute path (set
`ANAKRISIS_COLLECTION_MODE` to `cloud` or `local` in `env` as above):

```json
{
  "mcpServers": {
    "anakrisis": {
      "command": "python3",
      "args": ["/path/to/anakrisis/anakrisis.py"],
      "env": { "ANAKRISIS_COLLECTION_MODE": "cloud" }
    }
  }
}
```

Installing as a package (`pip install .`) adds an `anakrisis-server` command you can
use in place of `python3 /path/to/anakrisis.py`. The repository also ships a
project-scoped `.mcp.json`, so clients that support project configuration (such as
Claude Code) pick the server up when launched from the repo root.

</details>

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
