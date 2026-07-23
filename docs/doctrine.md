# Doctrine Reference

Anakrisis separates logic from policy. The Python server (`anakrisis.py`) contains the
evaluation machinery — normalization, trigger matching, scoring, tier mapping,
rendering — while the doctrine files define *what* is evaluated: risk factors, hard
stops, tool catalogs, analysis rules, redaction profiles, and presentation policy.

The doctrine lives in three places:

```
doctrine/            # 10 YAML files: rules, catalogs, and tool doctrines
playbooks/           # Per-investigation-type playbooks (YAML)
report_templates/    # Report skeletons (Markdown)
```

## How doctrine is loaded

- All YAML is parsed with `yaml.safe_load`. Doctrine files must therefore be plain
  YAML: no custom tags, no anchors that resolve to Python objects, no executable
  constructs.
- Files are cached by path with modification-time invalidation. Editing a doctrine
  file takes effect on the next tool call — no server restart required.
- Loading is defensive. A missing file logs a warning, a malformed file logs an error, and either degrades to a
  built-in fallback (for example, a minimal heuristic risk assessment) instead of
  crashing the server. The server assumes doctrine correctness: it validates shapes
  defensively but does not semantically lint your rules.

## The trigger engine

`risk_rules.yaml` and `disallowed_actions.yaml` share one deterministic trigger
schema, evaluated in `anakrisis.py`:

| Trigger type | Matches when |
|---|---|
| `contains_any` | any of `values` appears as a substring of the field |
| `equals_any` | the field exactly equals one of `values` |
| `not_contains_any` | none of `values` appears in the field (optionally gated with `evaluate_if_field_non_empty: true`) |
| `missing_any` | any of the listed `fields` is empty after normalization (or, for enum fields, equals `unknown`) |

All matching runs against normalized text: trimmed, lowercased, with internal
whitespace collapsed. Write trigger `values` as lowercase phrases; multi-word phrases
match as substrings of the normalized input.

## Quiet-by-default presentation

The advisory tools (MissionBrief, CourseCorrection, RulesOfEngagement) do not emit
warnings, hard stops, approvals, controls, or audit checklists on every call. These
sections surface only when the input actually trips a trigger:

- a **substantive** risk factor fires — an action/intent signal such as bypass,
  impersonation, or automation, not merely missing optional planning fields;
- a hard-stop rule in `disallowed_actions.yaml` matches the constraints text; or
- an action-safety keyword (ToS / privacy / legal / operational) matches.

Two consequences matter when authoring doctrine:

1. `missing_any` factors still contribute to the score and tier, but on their own
   they never flip a tool into warning mode. Use them to lower assessment confidence,
   not to nag.
2. Hard stops are sourced only from the deterministic `rules:` list in
   `disallowed_actions.yaml`. The legacy static lists in that file are a fallback
   used only when no `rules:` are defined, which prevents the full prohibition list
   from being dumped on every call.

This gates *presentation* only. Classification, scoring, and tier mapping are
unchanged whether or not the warning sections render.

---

## doctrine/risk_rules.yaml

The core scoring doctrine. Consumed by `MissionBrief` and `CourseCorrection`.

| Top-level key | Contents |
|---|---|
| `meta` | Version, last-updated date, owner, change log |
| `scope` | One-line statement of what the file governs |
| `inputs.fields` | The seven planning inputs (`goal`, `what_you_have`, `constraints`, `actor_role`, `method_class`, `jurisdiction_country`, `jurisdiction_state`), with types, defaults, and allowed enum values |
| `normalization` | Trim/lowercase/whitespace rules and the missing-field definition |
| `catalogs` | `approvals` and `controls` — id-to-label/description maps referenced by tiers and mitigations |
| `evaluation_model` | Scoring method (sum of triggered factor scores, floor 0, cap 20, dedupe by factor id), tier mapping (range match with tie-breakers), and approvals/controls aggregation (union of tier- and factor-level) |
| `risk_factors` | 12 factors, each with `id`, `name`, `score`, `description`, `rationale`, `evidence_fields`, and a list of `triggers` |
| `risk_tiers` | Four tiers with score ranges, `response_mode`, `required_approvals`, `mandatory_controls`: `TIER_LOW` (0–3), `TIER_MEDIUM` (4–8), `TIER_HIGH` (9–14), `TIER_CRITICAL` (15–20) |
| `mitigations.by_factor_id` | Per-factor mandatory controls and recommended actions |
| `explainability` | Schema for a richer audit output; marked `status: future` and not yet emitted by the server |
| `test_cases` | 10 input/expected-output cases for validating scoring changes |

Factor scores range from 2 (missing context, urgency) through 8 (harassment/doxxing
intent). Each factor counts once (scoring deduplicates by factor id), so a single
severe factor can reach `TIER_MEDIUM` on its own, while `TIER_HIGH` and above require
stacked signals.

**Customizing safely**

- Keep factor `id` values stable: `mitigations.by_factor_id` and the substantive/
  non-substantive gating key off them.
- Keep tier ranges contiguous over 0 to the score cap. Overlaps resolve to the
  higher `min_score`; gaps fall back to the closest tier, but neither situation is
  intended.
- When adding a factor, decide whether it is substantive (any non-`missing_any`
  trigger) or context-only (`missing_any` only) — this determines whether it can
  surface warning sections by itself.
- After any edit, walk the `test_cases` entries by hand or with a small script and
  confirm the expected factor ids, scores, and tiers still hold.

## doctrine/disallowed_actions.yaml

Hard stops and prohibited-action taxonomies. Consumed by `MissionBrief` and
`CourseCorrection` (via hard-stop evaluation against the `constraints` field).

| Top-level key | Contents |
|---|---|
| `rules` | Deterministic hard stops (preferred). Each has `id`, `text`, and `triggers` evaluated against the normalized constraints text |
| `baseline_prohibited`, `passive_only_prohibited`, `unauthorized_prohibited` | Legacy static lists, used only as a fallback when no `rules:` exist |
| `tos_violations`, `privacy_violations`, `legal_violations` | Advisory taxonomies for documentation; not evaluated by the server |

The shipped rules cover impersonation, bypassing access controls, social engineering
and pretexting, malware/exploits/service disruption, and illegal sexual content
involving minors.

**Customizing safely**

- Add new hard stops as entries in `rules:` with a `contains_any` trigger on
  `constraints`. Items placed only in the legacy lists will not fire while `rules:`
  is non-empty.
- Rule `text` is shown verbatim to the investigator; keep it a short, imperative
  prohibition.

## doctrine/actor_profiles.yaml

Role-based risk context: modifiers, oversight expectations, documentation
requirements, and escalation triggers for 11 investigator roles (private individual,
student/hobbyist, licensed investigator, corporate security, journalist, academic
researcher, NGO/humanitarian, legal team, law enforcement, incident response, threat
intelligence analyst).

| Top-level key | Contents |
|---|---|
| `version`, `description`, `disclaimer` | File metadata and not-legal-advice disclaimers |
| `default_policy.unknown_actor_role` | Conservative defaults when no role is given (modifier 2, oversight recommended) |
| `actor_profiles` | Per-role `display_name`, `risk_modifier`, `oversight_recommended`, `notes`, `common_constraints`, `recommended_documentation`, `escalation_triggers` |

**Status:** advisory. The server loads this file through a reserved loader, but the
`risk_modifier` values are not yet folded into scoring — role-driven risk today comes
from `risk_rules.yaml` triggers on the `actor_role` field. Treat this file as
reference doctrine and a staging area for the full evaluator.

## doctrine/jurisdiction_rules.yaml

High-level jurisdictional risk modifiers for 13 countries/regions (with US state
subregions), on a 0–3 scale.

| Top-level key | Contents |
|---|---|
| `modifier_scale` | Meaning of modifier values 0 through 3 |
| `stacking_policy` | How jurisdiction modifiers are intended to combine with actor and method modifiers (additive, subregion replaces country, unknown jurisdiction dominates) |
| `disclaimer` | Not-legal-advice statements |
| `default_policy.unknown_jurisdiction` | Modifier 2 with escalation required |
| `countries` | Per-country `display_name`, `risk_modifier`, `escalation_required`, `notes`, `special_flags`, and optional `subregions` |

**Status:** advisory. As the file itself notes, these modifiers only affect scoring
if the server explicitly integrates them; today MissionBrief uses the jurisdiction
fields for follow-up questions and `missing_any` context scoring. Laws change —
review entries with counsel before relying on them.

## doctrine/method_classes.yaml

Collection-method taxonomy used to reason about interaction level and escalation.
Defines six classes with risk modifiers: `passive_only` (−1), `passive_plus` (0),
`active_interaction` (2), `automation_bulk` (3), `intrusive_access` (4), and
`unknown` (2).

| Top-level key | Contents |
|---|---|
| `version`, `description`, `disclaimer` | File metadata |
| `default_policy.unknown_method_class` | Conservative fallback |
| `method_classes` | Per-class `display_name`, `risk_modifier`, `interaction_level`, `data_sensitivity`, `notes`, `examples`, `common_risks`, `requires`, `prohibited_if` |

**Status:** advisory, like actor profiles and jurisdiction rules. Method-driven
scoring currently happens through `risk_rules.yaml` triggers on the `method_class`
field (note that those triggers use the enum values declared in
`risk_rules.yaml` `inputs.fields.method_class.allowed_values`, e.g.
`passive_public_sources`, `automation_or_bulk` — keep the two files aligned if you
extend either taxonomy).

## doctrine/assigntools.yaml

The offline OSINT tool catalog consumed by `AssignTools`: 19 categories, roughly 170
tools.

| Top-level key | Contents |
|---|---|
| `meta` | Version, last-updated date, notes |
| `categories` | Category key to `{label, description, tools}` |

Each tool entry carries `id`, `name`, `url`, `description`, `tags`, `cost`
(`free` / `freemium` / `paid` / `unknown`), and `account_required`. Categories
include company research, registries, DNS/WHOIS, internet scanning, email, phone,
people records, geospatial, search engines, image search, social media, username
lookup, Google dorking, safety, OSINT directories, vehicles, document metadata, and
cryptocurrency.

**Customizing safely**

- Ranking is keyword overlap against `name`, `tags`, and `description` — rich,
  accurate tags are the main lever for recommendation quality.
- New category keys become addressable via `artifact_type` immediately; add common
  aliases to the synonym map in `anakrisis.py` if investigators are likely to use
  different words for them.
- The catalog is never fetched or validated online. Review links and cost/account
  metadata periodically.

## doctrine/text_analyzer.yaml

The analysis doctrine embedded into the `TextAnalyzer` prompt.

| Top-level key | Contents |
|---|---|
| `meta` | Tool name, doctrine version, purpose, scope (investigator-facing; PII surfaced, never redacted) |
| `highlight_categories` | 13 artifact categories (email, phone, username, domain, IP, crypto address, name, physical address, government ID, financial info, device identifier, organization, date/time) with priorities |
| `osint_notes` | Intent, tone, and stance classification taxonomies with example trigger phrases |
| `warning_categories` | 9 warning types (threat, extortion, fraud, doxxing, phishing/malware, illegal activity, harassment, covert coordination, self-harm) with severity and per-warning investigator guidance |
| `pivot_rules` | Passive pivot actions keyed by artifact type |
| `response_structure` | The enforced section order: language detection, translation, key artifacts, OSINT notes, content warnings, recommended pivots |

**Customizing safely**

- The whole file is serialized into the prompt, so wording is behavior: keep
  descriptions imperative and unambiguous.
- Warning triggers should be direct indicators, not topics — the doctrine explicitly
  instructs the model not to warn on vague mentions.
- Keep every pivot action passive; this doctrine is the guardrail that prevents the
  analysis step from recommending interactive collection.

## doctrine/graph_builder.yaml

The relationship-mapping doctrine embedded into the `GraphBuilder` prompt.

| Top-level key | Contents |
|---|---|
| `meta` | Name, version, purpose, scope, and principles (correlation is not attribution, preserve uncertainty, conservative confidence) |
| `node_types` | 12 entity types with labels and definitions |
| `relationship_types` | 13 relationship types, from `owns`/`controls` down to `possible_match` |
| `confidence_levels` | `confirmed` / `probable` / `possible`, each with an explicit evidence requirement |
| `graph_rules` | 9 mapping rules (no entity merging without confirmation, flag single-source inferences, surface contradictory evidence) |
| `analyst_observations` | Patterns worth surfacing without drawing conclusions |
| `response_structure` | Section order ending in the Obsidian-compatible graph note |

**Customizing safely**

- Add new node or relationship types rather than overloading `associated_with`;
  vague types erode the value of confidence levels.
- If you relax a confidence definition, re-read `graph_rules` — the two sections are
  designed to reinforce each other, with `possible` doing the work of keeping
  unverified links visible but labeled.

## doctrine/report_redaction.yaml

The publication-safety doctrine embedded into the `ReportRedaction` prompt.

| Top-level key | Contents |
|---|---|
| `meta` | Name, version, purpose, scope, out-of-scope list, design principles |
| `redaction_profiles` | `public_release`, `journalist_release`, `client_release` — each lists the categories it redacts |
| `redaction_categories` | 17 categories, each with a description and a structured `replacement_token` pattern such as `[REDACTED_SOURCE_{N}]` |
| `token_rules` | Consistent tokens per entity, no token reuse across entities, prefer partial redaction |
| `preservation_rules` | What to keep: findings, timelines, general methodology, public-interest information |
| `residual_risk_rules` | Definitions and examples for low/medium/high re-identification risk |
| `residual_risk_assessment_guidance` | Cumulative, mosaic-aware assessment rules |
| `response_structure.ordered_sections` | Profile, redacted report, redaction log, preserved information, residual risk assessment, reviewer notes |

**Customizing safely**

- A new audience is just a new profile: name it, describe it, and list its
  `categories_to_redact`. The `audience` parameter of `ReportRedaction` selects it
  by key.
- Every category referenced by a profile must exist in `redaction_categories` with a
  unique token pattern; the numbered token scheme is what makes the redaction log
  auditable.
- Redaction here errs toward preservation of analytical value. If your threat model
  is stricter, tighten `preservation_rules` before adding categories.

## doctrine/output_policy.yaml

Global response formatting policy. MissionBrief, CourseCorrection,
RulesOfEngagement, and AssignTools consume it via a merged global-plus-override
lookup; TextAnalyzer, GraphBuilder, and ReportRedaction embed only their per-tool
override section into the prompts they build. CreateCase and ReportTemplate do not
currently consult it (their `tool_overrides` entries are reserved).

| Top-level key | Contents |
|---|---|
| `meta`, `style`, `summary` | Concise, direct, bullets-first presentation defaults |
| `limits` | Bullet caps, target/hard line limits, words per bullet |
| `section_policy` | Omit empty sections, lead with key findings, prefer actionable items |
| `priority_order` | What survives truncation first (hard stops, then risk tier, then triggered risks, ...) |
| `exceptions.allow_expansion_when` | High risk, multiple hard stops, severe content warnings, legal escalation |
| `tool_overrides` | Per-tool modes and limits (e.g., `AssignTools.max_results: 15`, `GraphBuilder.max_bullets_per_section: 10`) |
| `fallback` | What to do when output is too long or empty |

`output_policy.yaml` affects presentation only. It never changes risk scoring, hard
stops, approvals, controls, classifications, or investigative logic — if doctrine and
output policy ever appear to conflict inside a doctrine-bound prompt, doctrine
controls content and output policy controls brevity. The server additionally clamps
policy integers to sane ranges (for example, `max_results` is capped at 30), so a
typo cannot produce unbounded output.

## playbooks/

Per-investigation-type playbooks, one YAML file per type, keyed by filename stem.
Shipped playbooks: `background_check.yaml`, `general_investigation.yaml`,
`threat_assessment.yaml`.

Common structure: `investigation_type`, `description`, `risk_baseline`, `phases`,
`safe_first_steps`, `authorization_requirements`, `data_sources` (allowed vs.
restricted), `prohibited_methods`, plus type-specific sections such as
`escalation_triggers` (threat assessment) or `retention_and_disposal`.

Consumed by `MissionBrief`: when the goal classifies to a type whose playbook exists,
that playbook's `safe_first_steps` populate the Safe Next Steps section (a generic
list is used otherwise).

**Customizing safely**

- To add a playbook for an existing classification (e.g., `fraud_investigation`),
  name the file after the classification id — the match is exact on the filename
  stem. To add an entirely new classification, also extend the keyword classifier in
  `anakrisis.py`.
- Keep `safe_first_steps` genuinely safe: passive, documented, authorization-first.
  These render without any risk gating, on every matching MissionBrief call.

## report_templates/

Markdown report skeletons consumed by `ReportTemplate`, resolved in this order:

1. `<investigation_type>_<audience>.md`
2. `generic_<audience>.md`
3. `default.md`

The shipped `default.md` is a full OSINT intelligence report skeleton: metadata
header (report/case id, handling and TLP marking, reporting period), executive
summary, key judgments with confidence scale, intelligence requirement, scope and
constraints, methodology, findings, and supporting sections.

**Customizing safely**

- Add audience- or type-specific templates using the naming convention above; no
  code changes are needed.
- Keep placeholders in the `[bracketed]` style so the generated instructions ("fill
  in all sections marked with placeholders") stay accurate.
- Templates are structure only. Never bake case data, names, or organizational
  identifiers into a template file.

---

## General authoring rules

1. **YAML-safe only.** Everything is parsed with `yaml.safe_load`. Quote strings
   containing `:` or leading special characters; keep values plain scalars, lists,
   and maps.
2. **Deterministic by design.** The advisory tools promise reproducible output for
   identical input. Prefer explicit trigger phrases over cleverness, and record
   meaningful changes in the `meta.change_log` where a file has one.
3. **Lowercase trigger values.** All matching runs on normalized (lowercased,
   whitespace-collapsed) text; mixed-case trigger values will still match, but
   writing them lowercase keeps intent obvious.
4. **Mind the quiet-by-default gate.** Ask, for every new rule: should this render
   warnings on its own? Substantive triggers do; `missing_any` triggers do not.
5. **Validate with the test cases.** `risk_rules.yaml` ships expected outcomes for
   ten scenarios — keep them passing, and add cases alongside new factors.
6. **Advisory means advisory.** No doctrine edit turns Anakrisis into an enforcement
   layer. Warnings surface exposure; responsibility for actions taken remains with
   the investigator.
