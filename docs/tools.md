# Tool Reference

Anakrisis exposes nine MCP tools. All of them are advisory: they classify, score,
structure, and recommend, but none of them collects data, executes actions, or blocks
execution. Every tool returns plain text (Markdown-formatted) and validates its own
required parameters, returning a short error message when a required field is missing.

Collection itself is carried out by the model driving the server, not by the tools: a
cloud model has web access and runs the searches and lookups these tools recommend,
while a local model has none and leaves the collection to you.

All string parameters default to an empty string unless noted otherwise. Presentation
(bullet caps, section ordering, grouping) is governed by `doctrine/output_policy.yaml`;
see [doctrine.md](doctrine.md) for details.

The tools fall into three groups:

| Group | Tools | Behavior |
|---|---|---|
| Advisory / risk | `MissionBrief`, `CourseCorrection`, `RulesOfEngagement` | Deterministic classification and keyword/trigger evaluation in the server |
| Workspace / documentation | `CreateCase`, `ReportTemplate`, `AssignTools` | Controlled filesystem scaffolding and static catalog/template lookup |
| Doctrine-bound analysis | `TextAnalyzer`, `GraphBuilder`, `ReportRedaction` | Return a doctrine-bound prompt for the host LLM to execute |

---

## MissionBrief

Pre-investigation planning, classification, and safety assessment. This is the
primary entry point at the start of an investigation.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `goal` | string | yes | What the investigation is trying to accomplish |
| `what_you_have` | string | no | Starting artifacts (e.g., a username, a domain) described in general terms |
| `constraints` | string | no | Authorization basis, scope limits, and operating constraints |
| `actor_role` | string | no | Investigator role context (e.g., `licensed_investigator`, `journalist`) |
| `method_class` | string | no | Intended collection approach (e.g., `passive_public_sources`) |
| `jurisdiction_country` | string | no | Primary country involved |
| `jurisdiction_state` | string | no | Subregion/state, if relevant |

### What it produces

An "Investigation Planning Assessment" containing:

- **Key Findings** — the investigation classification (keyword-based:
  `background_check`, `threat_assessment`, `fraud_investigation`, `person_location`,
  `digital_footprint_analysis`, or `general_investigation` as the default), plus the
  risk tier, response mode, and trigger counts when a risk signal fires.
- **Safe Next Steps** — `safe_first_steps` drawn from any matching playbook in
  `playbooks/`, with a generic fallback list when no playbook matches.
- When a substantive risk factor or hard stop fires, additional sections:
  **Risk Factors** (scored factor summaries from `doctrine/risk_rules.yaml`),
  **Hard Stops** (deterministic rules from `doctrine/disallowed_actions.yaml`),
  **Required Approvals** and **Mandatory Controls** (tier- and factor-level, resolved
  through the catalogs in `risk_rules.yaml`), **Mitigations**, an **Audit Checklist**,
  and targeted follow-up questions (jurisdiction, actor role, method class).

Risk scoring is deterministic: normalized inputs are evaluated against the trigger
definitions in `risk_rules.yaml`, factor scores are summed (deduplicated by factor id,
clamped to the configured floor/cap), and the total maps to a tier range
(`TIER_LOW` through `TIER_CRITICAL`).

MissionBrief is quiet by default: missing optional planning fields still contribute to
the score, but warnings, hard stops, approvals, and controls only surface when an
actual action/intent signal (or a hard-stop rule) matches the input.

### When to use

At intake, before any collection is planned. Re-run it if the goal or scope changes
materially.

### Limits

- Performs no collection, search, or verification of its own; it evaluates only the text
  you supply. Your agent can and will go collect — this is the tool you run beforehand to
  decide what collecting is worth the risk.
- Does not halt or gate execution — approvals and controls are advisory.
- Classification is keyword-based and intentionally coarse; it selects playbooks and
  framing, not legal conclusions.

---

## CourseCorrection

Mid-investigation guidance and risk re-assessment as new artifacts, leads, or
roadblocks appear.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `current_phase` | string | yes | One of `intake`, `planning`, `discovery`, `validation`, `reporting` |
| `new_artifacts` | string | no | Description of newly obtained artifacts or findings |
| `constraints` | string | no | Current operating constraints |

### What it produces

A "Course Correction" summary containing:

- **Key Findings** — the current phase, plus the updated risk tier and any escalation
  alert when a trigger fires.
- **Phase Actions** — a fixed, phase-specific checklist (e.g., during `validation`:
  cross-reference findings across independent sources, document confidence levels,
  seek contradictory information).
- When a risk factor, hard stop, or escalation keyword fires: **Risk Factors**
  (re-scored using `new_artifacts` and `constraints`), **Avoid Next** (matched hard
  stops), and a **Before Next Phase** checklist.

An escalation alert is raised when `new_artifacts` mentions personal identifiers
(e.g., a real name, address, or employer), reinforcing heightened privacy handling.

### When to use

At phase transitions, after significant new findings, or whenever scope shifts during
an active investigation.

### Limits

- Updates risk posture only; it performs no validation of the artifacts themselves.
- Phase guidance is static doctrine, not case-specific analysis.
- Quiet by default: with no triggered signals, it returns only phase guidance.

---

## RulesOfEngagement

Advisory interlock to run before executing a potentially risky action.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `proposed_action` | string | yes | The specific action under consideration |
| `context` | string | no | Supporting context for the review |

### What it produces

The proposed action and context are evaluated against `action_rules:` in
`doctrine/disallowed_actions.yaml`. Each rule carries a `severity`
(`hard_stop` / `high` / `elevated`) and a risk `category`:

- **ToS risk** — scraping, bulk collection, rate-limit evasion, research-persona accounts
- **Privacy risk** — pretexting, physical surveillance
- **Legal risk** — impersonating a real person, accessing restricted content, authentication bypass, credential use
- **Operational risk** — contacting or interacting with the target (including from a research persona), service disruption

Three outcomes:

- **Hard stop matched** → `🛑 ACTION PROHIBITED`, listing each matched prohibition, the
  triggering warnings, **Safer Alternatives**, and a **Do Not Proceed** block. Hard stops
  are not clearable by authorization or supervisor approval.
- **Warnings only** → `🚨 ACTION SAFETY ASSESSMENT` with a safety level (elevated for one
  or two warnings, high risk requiring review at three or more), the warnings, **Safer
  Alternatives**, and a **Before Proceeding** checklist.
- **No rule matched** → `🔍 ACTION REVIEW` stating explicitly that this is **not** a
  clearance. An unrecognized action is unassessed, not safe. The investigator is asked to
  confirm the action is passive, authorized, and in scope, and to restate it plainly and
  re-run if it involves a target individual.

### When to use

Immediately before any individual action that touches a platform, a person, or
non-trivial collection — especially anything interactive or automated.

### Limits

- Flags risk exposure; it does not block the action or make legality determinations.
- Detection is keyword-based against the text of the proposed action and context.
  `all_of` triggers make multi-word concepts resilient to interposed words ("fake
  Instagram account" matches `["fake", "account"]`), but a deliberately euphemistic
  description can still evade the ruleset. This is why a no-match result is reported as
  unassessed rather than clean.

---

## ReportTemplate

Generates a structured documentation template for an investigation report.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `investigation_type` | string | no | Defaults to `general_investigation` when empty |
| `audience` | string | no | Defaults to `internal` when empty |
| `constraints` | string | no | Reserved for future template selection logic |

### What it produces

The template body is resolved from `report_templates/` in this order:

1. `<investigation_type>_<audience>.md`
2. `generic_<audience>.md`
3. `default.md`

The resolved template is wrapped with a metadata header (investigation type, audience)
and usage instructions: fill placeholders, distinguish facts from inferences, document
what was not found, and include confidence levels and limitations.

### When to use

During the reporting phase, before drafting; the template enforces a consistent
structure (executive summary, key judgments, scope, methodology, findings, sources,
limitations).

### Limits

- Provides structure only — it never inserts case data.
- Template coverage depends on the files present in `report_templates/`; the shipped
  default is a comprehensive general-purpose OSINT report skeleton.

---

## AssignTools

Recommends external OSINT tools from the static catalog in
`doctrine/assigntools.yaml`.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `artifact_type` | string | no | The artifact you are pivoting from (e.g., `email`, `username`, `domain`) |
| `goal` | string | no | What you are trying to learn |
| `constraints` | string | no | Operating constraints; contributes to keyword scoring |
| `max_results` | integer | no | Result cap; `0` uses the output-policy default (15, hard cap 30) |

### What it produces

A ranked recommendation list. Common synonyms are mapped to catalog categories
(`handle` to `username`, `ip address` to `internet_scan`, and so on). Scoring is a
simple deterministic heuristic: a large boost when the artifact type matches a catalog
category, plus keyword overlap between the goal/constraints text and each tool's name,
tags, and description, with minor boosts for free tools and pivot-tagged tools.

Each recommendation includes the tool name, catalog id, cost, whether an account is
required, a one-line rationale, and the link. Results are grouped by category by
default (per `output_policy.yaml`). If the artifact type is not a known category, the
tool lists the available categories and still returns best-effort matches. Every
response ends with a usage reminder covering authorization, passive-first collection,
and documentation.

### When to use

During planning or discovery, when deciding which external resource fits the artifact
in hand.

### Limits

- Catalog recommender only: it does not execute tools, connect to the internet, or
  verify that listed services are still available.
- Ranking quality depends on catalog metadata (tags, descriptions) in
  `assigntools.yaml`.

---

## CreateCase

Initializes a structured investigation workspace on the local filesystem.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `case_name` | string | yes | 1–64 characters; letters, numbers, spaces, `_`, `-`; must start with a letter or number |
| `overwrite` | boolean | no | Default `false`; when `false`, an existing case is left untouched |

### What it produces

A case directory under `~/anakrisis/cases/<case_name>/` containing:

- **Files:** `objective.md`, `notes.md`, `report.md`, `graph.md`, `metadata.json`
- **Subdirectories:** `Sources/`, `Screenshots/`, `PDFs/`, `Intelligence/`, `OtherEvidence/`

Each file is created with a section skeleton (e.g., `objective.md` has Purpose, Scope,
Constraints, Legal/Ethical Notes, Success Criteria). `metadata.json` records the case
name, creation timestamp, and status. The response confirms the path and counts of
created folders and files, and points you at `objective.md` as the next step.

Case names are validated against a conservative pattern that rejects path traversal
and unusual characters. Scaffolding is idempotent: even with `overwrite=true`, only
missing files and folders are created — existing content is never deleted.

### When to use

Once per investigation, at intake, before collection begins.

### Limits

- Controlled filesystem operations only; it does not access external data sources.
- It will not overwrite an existing case unless explicitly instructed.

---

## TextAnalyzer

Doctrine-guided triage of textual artifacts: messages, emails, posts, chat logs.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `text` | string | yes | The text to analyze |
| `investigator_language` | string | no | Response (and translation target) language; defaults to `English` |
| `constraints` | string | no | Operational constraints passed into the prompt |

### What it produces

TextAnalyzer does not analyze the text itself. It embeds the full doctrine from
`doctrine/text_analyzer.yaml` (plus the TextAnalyzer overrides from
`output_policy.yaml`) into a doctrine-bound prompt and returns that prompt for the
host LLM to execute. The doctrine enforces a fixed response structure:

1. **Language Detected**
2. **Translation** (omitted when already in the investigator's language)
3. **Key Artifacts Identified** — high-value intelligence and PII, grouped by
   category (emails, phones, usernames, domains, IPs, crypto addresses, names,
   addresses, government IDs, financial info, device identifiers, organizations,
   dates), with exact values preserved and never redacted
4. **OSINT Notes** — intent, tone, stance, and sentiment classification
5. **Content Warnings** — triggered categories (threat, extortion, fraud, doxxing,
   phishing/malware, illegal activity, harassment, covert coordination, self-harm)
   with severity and per-warning investigator guidance; omitted when nothing fires
6. **Recommended Pivots** — passive, artifact-keyed next steps from the doctrine's
   pivot rules

### When to use

Whenever a textual artifact enters the case: suspicious messages, scam emails,
threatening posts, chat exports.

### Limits

- Analysis and triage aid: it does not itself collect, scrape, or execute the pivots it
  recommends — executing them is the agent's job, and worth running past
  `RulesOfEngagement` first.
- PII in the submitted text is deliberately surfaced, not redacted — this tool is for
  investigator triage, not publication (use `ReportRedaction` for that).
- Content warnings fire only on direct indicators in the text, not vague topic
  mentions.

---

## GraphBuilder

Doctrine-guided relationship mapping from investigative notes and findings.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `notes` | string | yes | Investigative notes, artifacts, or findings to map |
| `case_context` | string | no | Case background injected into the prompt |
| `investigator_language` | string | no | Response language; defaults to `English` |

### What it produces

Like TextAnalyzer, this tool returns a doctrine-bound prompt (built from
`doctrine/graph_builder.yaml`) for the host LLM to execute. The doctrine defines
12 node types (person, username, email, phone, domain, IP address, company,
organization, cryptocurrency address, social account, website, location), 13
relationship types (`uses`, `owns`, `controls`, `communicates_with`,
`associated_with`, `possible_match`, and others), and three conservative confidence
levels (`confirmed`, `probable`, `possible`), each with explicit evidence
requirements. The enforced output structure is:

1. **Entities Identified**
2. **Relationships** — `SOURCE -> RELATIONSHIP_TYPE -> TARGET` with confidence
3. **Confidence Assessment**
4. **Supporting Evidence** — a cited basis for every relationship
5. **Analyst Observations** — patterns (username reuse, shared infrastructure,
   temporal clustering) surfaced without conclusions
6. **Verification Needed**
7. **Recommended Pivots**
8. **Obsidian Graph Note** — a wikilink-formatted Markdown note suitable for a case
   workspace

The graph rules are deliberately conservative: correlation is never treated as
attribution, entities are not merged without confirmed identity, single-source
inferences are flagged for verification, and contradictory evidence is surfaced
rather than suppressed.

### When to use

After discovery has produced enough artifacts to relate — typically during validation,
or whenever the case's entity picture needs to be consolidated.

### Limits

- Relationship-mapping aid only: it does not verify relationships, perform
  attribution, or collect data.
- Visualization, storage, and rendering are out of scope; the Obsidian note is plain
  Markdown output.

---

## ReportRedaction

Doctrine-guided redaction for preparing reports for publication or controlled
disclosure.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `report_text` | string | yes | The report or excerpt to redact |
| `audience` | string | no | Redaction profile: `public_release` (default), `journalist_release`, or `client_release` |
| `redaction_notes` | string | no | Additional case-specific redaction instructions |
| `investigator_language` | string | no | Response language; defaults to `English` |

### What it produces

Returns a doctrine-bound prompt (built from `doctrine/report_redaction.yaml`) for the
host LLM to execute. The doctrine defines audience-specific profiles — maximum
redaction for public release, moderate for vetted journalists, tailored for the
commissioning client — 17 redaction categories (source identity, confidential
sources, PII/SPII, contact details, government and financial identifiers, internal
case references, witness and minor identities, public-figure private details, and
investigative-sensitive material).

Sensitive material is replaced with structured, numbered tokens (for example
`[REDACTED_SOURCE_1]`) rather than silently deleted, with consistent tokens for
repeated references to the same entity. The enforced output structure is:

1. **Selected Redaction Profile** — with rationale
2. **Redacted Report** — full text with tokens applied, analytical value preserved
3. **Redaction Log** — token, category, and reason for every redaction
4. **Preserved Information** — what was intentionally retained, and why it is safe
5. **Residual Risk Assessment** — low/medium/high re-identification risk from the
   remaining context, assessed cumulatively
6. **Reviewer Notes** — ambiguous cases and items needing human review

Preservation rules bias toward keeping findings, timelines, methodology at a general
level, and public-interest information, preferring partial redaction over removal.

### When to use

At the very end of the reporting phase, once the report content is final and before
any external sharing.

### Limits

- Publication-safety aid only: it does not encrypt data, modify files, enforce access
  controls, or perform legal review.
- Residual-risk assessment is analytical guidance, not a guarantee against
  re-identification; a human review pass before publication is still expected.
