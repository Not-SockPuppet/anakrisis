#!/usr/bin/env python3
"""
The Anakrisis Protocol MCP Server - Ethics-aware OSINT decision and analysis system
"""
import sys
import os
import logging
from pathlib import Path
import re
import json
from datetime import datetime
import yaml
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("anakrisis")

# Initialize MCP server
mcp = FastMCP("anakrisis")

# ---------------------------------------------------------------------------
# COLLECTION MODE -- can the host actually go and collect?
#
# Anakrisis plans collection, and it is useful to offer to *run* the next step
# ("want me to search for that handle?"). Whether that offer makes sense depends
# on what is driving the server: a cloud assistant usually has web search, a
# local Ollama model usually has nothing but its own weights. Offering to search
# when the model cannot is worse than not offering.
#
# MCP cannot answer this for us. The protocol negotiates client *capabilities*
# (sampling, elicitation, roots, tasks) and carries a clientInfo name -- it does
# not report which model is loaded, and a server is deliberately not allowed to
# enumerate the host's own tools. So there is no reliable auto-detection, and
# any claim otherwise would be guesswork dressed as a feature.
#
# What we do instead, in order of trust:
#   1. ANAKRISIS_COLLECTION_MODE=cloud|local -- explicit, always wins. Set it in
#      the same mcp config block that launches the server.
#   2. clientInfo.name heuristic -- good for hosts that are unambiguous
#      (Claude Desktop is cloud, LM Studio is local). Deliberately conservative:
#      anything that can be pointed at either backend stays unknown.
#   3. Unknown -> phrase the offer conditionally rather than assume. This is the
#      default, and it degrades gracefully with no configuration at all.
# ---------------------------------------------------------------------------
COLLECTION_MODE_ENV = "ANAKRISIS_COLLECTION_MODE"

# Hosts that ship with hosted models and web access. Substring match on clientInfo.name.
_CLOUD_CLIENT_HINTS = (
    "claude-ai", "claude desktop", "claude code", "claude",
    "chatgpt", "openai", "gemini", "copilot", "perplexity",
)
# Hosts that are local-inference front ends by nature.
_LOCAL_CLIENT_HINTS = (
    "ollama", "lm studio", "lmstudio", "jan", "gpt4all",
    "localai", "llamacpp", "llama.cpp", "text-generation-webui", "oobabooga",
)
# Hosts that can be pointed at either a cloud or a local backend. Never guessed;
# these are exactly the users who should set the env var.
_AMBIGUOUS_CLIENTS = ("continue", "cline", "roo", "zed", "cursor", "windsurf", "librechat", "open webui")


def _client_name() -> str:
    """clientInfo.name for the current request, lowercased. Empty if unavailable.

    Read from the lowlevel contextvar rather than by threading a Context
    parameter through all nine tools, which would change every signature for
    one advisory string.
    """
    try:
        from mcp.server.lowlevel.server import request_ctx
        params = request_ctx.get().session.client_params
        return str(getattr(getattr(params, "clientInfo", None), "name", "") or "").lower()
    except Exception:
        return ""


def collection_mode() -> str:
    """Return "cloud", "local", or "unknown". Never raises."""
    override = str(os.environ.get(COLLECTION_MODE_ENV, "")).strip().lower()
    if override in ("cloud", "local"):
        return override
    if override and override != "auto":
        logger.warning("%s=%r is not cloud/local/auto; falling back to auto", COLLECTION_MODE_ENV, override)

    name = _client_name()
    if not name:
        return "unknown"
    if any(h in name for h in _AMBIGUOUS_CLIENTS):
        return "unknown"
    if any(h in name for h in _LOCAL_CLIENT_HINTS):
        return "local"
    if any(h in name for h in _CLOUD_CLIENT_HINTS):
        return "cloud"
    return "unknown"


def render_collection_offer(suggestions) -> str:
    """Offer to run the next collection step, phrased for what the host can do.

    cloud   -- offer directly; the assistant can act on it.
    local   -- no offer. Frame the same work as steps for the investigator, since
               a local model has no web access and a prompt it cannot honour is
               just noise.
    unknown -- offer conditionally, so it reads correctly either way.
    """
    items = [str(s).strip() for s in (suggestions or []) if str(s).strip()]
    if not items:
        return ""

    mode = collection_mode()
    if mode == "local":
        header = "Collection Steps (run these yourself)"
        lead = "No web access assumed for this host, so these are for you to carry out:"
    elif mode == "cloud":
        header = "Collection I Can Run"
        lead = "Say the word and I'll take these on:"
    else:
        header = "Suggested Collection"
        lead = "If your assistant has web access it can run these; otherwise they are yours to do:"

    return render_section(header, [lead] + items, max_items=8)


# Artifact -> a concrete, passive, public-source collection step. Keyed on words
# that show up in `what_you_have`. Everything here is first-pass and non-interactive
# by design; nothing that touches the target belongs in an unprompted offer.
_ARTIFACT_COLLECTION_HINTS = (
    (("username", "handle", "screenname", "screen name", "nickname", "alias"),
     "Run the username across platforms (Sherlock and Maigret cover the common ones) and note where it resolves"),
    (("email", "e-mail", "email address"),
     "Check the email against public breach-notification and reputation sources, and for linked public profiles"),
    (("phone", "mobile", "cell number", "phone number"),
     "Run the number through public reverse-lookup and carrier-identification sources"),
    (("domain", "website", "url", "site"),
     "Pull WHOIS, DNS records, and passive certificate transparency history for the domain"),
    (("company", "business", "employer", "organisation", "organization"),
     "Pull registry filings, listed officers, and public funding records for the company"),
    (("photo", "image", "picture", "profile pic", "avatar"),
     "Reverse-image search the photo across the major engines to find other places it appears"),
    (("ip", "ip address", "server", "hostname", "infrastructure"),
     "Check passive DNS and public internet-scan data for the address"),
    (("name", "full name", "real name"),
     "Search the name against public records, news archives, and professional directories"),
)


def suggest_collection(what_you_have: str, hard_stops=None):
    """Passive collection steps implied by the artifacts already in hand.

    Returns [] when a hard stop fired -- if the plan is blocked, the right next
    move is re-scoping it, not collecting more.
    """
    if hard_stops:
        return []
    haystack = str(what_you_have or "").lower()
    if not haystack.strip():
        return []

    # Word boundaries, not substrings: plain `"name" in haystack` fires on
    # "username", and `"ip"` fires on half the dictionary.
    seen, out = set(), []
    for keys, suggestion in _ARTIFACT_COLLECTION_HINTS:
        if suggestion in seen:
            continue
        if any(re.search(rf"\b{re.escape(k)}\b", haystack) for k in keys):
            out.append(suggestion)
            seen.add(suggestion)
    return out


# === CONFIGURATION ===
BASE_DIR = Path(__file__).parent
DOCTRINE_DIR = BASE_DIR / "doctrine"
PLAYBOOKS_DIR = BASE_DIR / "playbooks"
REPORT_TEMPLATES_DIR = BASE_DIR / "report_templates"

RISK_RULES_FILE = DOCTRINE_DIR / "risk_rules.yaml"
DISALLOWED_ACTIONS_FILE = DOCTRINE_DIR / "disallowed_actions.yaml"
JURISDICTION_RULES_FILE = DOCTRINE_DIR / "jurisdiction_rules.yaml"
ACTOR_PROFILES_FILE = DOCTRINE_DIR / "actor_profiles.yaml"
METHOD_CLASSES_FILE = DOCTRINE_DIR / "method_classes.yaml"
ASSIGNTOOLS_CATALOG_FILE = DOCTRINE_DIR / "assigntools.yaml"
TEXT_ANALYZER_FILE = DOCTRINE_DIR / "text_analyzer.yaml"
GRAPH_BUILDER_FILE = DOCTRINE_DIR / "graph_builder.yaml"
REPORT_REDACTION_FILE = DOCTRINE_DIR / "report_redaction.yaml"
OUTPUT_POLICY_FILE = DOCTRINE_DIR / "output_policy.yaml"

# Case workspace directory (user-local)
CASES_DIR = Path.home() / "anakrisis" / "cases"

# Case folder structure
CASE_SUBDIRS = ["Sources", "Screenshots", "PDFs", "Intelligence", "OtherEvidence"]

# Conservative case name policy (prevents path traversal / weird chars)
_CASE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$")

# === YAML CACHE ===
# Cache YAML by file path with mtime invalidation (reduces latency for repeated tool calls).
_YAML_CACHE: dict[str, dict] = {}


# === UTILITY FUNCTIONS ===

# --- Doctrine-driven risk evaluator helpers ---

def _norm_text(value: str) -> str:
    """Normalize free-text inputs for deterministic matching."""
    s = (value or "")
    # match normalization.doctrine: trim + collapse whitespace + lowercase
    s = " ".join(s.strip().split())
    return s.lower()


def _is_missing_field(field_name: str, normalized_value: str) -> bool:
    """Treat empty string (or enum == 'unknown') as missing per doctrine."""
    if not normalized_value:
        return True
    # For enum-ish fields, doctrine uses default 'unknown' as missing.
    if field_name in {"actor_role", "method_class"} and normalized_value == "unknown":
        return True
    return False


def _trigger_matches(trigger: dict, normalized_inputs: dict) -> tuple[bool, list[str]]:
    """Return (matched, evidence_snippets). Evidence is minimal and safe: matched tokens only."""
    if not isinstance(trigger, dict):
        return False, []

    ttype = str(trigger.get("type", "") or "").strip()
    field = str(trigger.get("field", "") or "").strip()

    # missing_any operates over 'fields'
    if ttype == "missing_any":
        fields = trigger.get("fields", [])
        if not isinstance(fields, list):
            return False, []
        missing = []
        for f in fields:
            f = str(f or "").strip()
            if not f:
                continue
            v = normalized_inputs.get(f, "")
            if _is_missing_field(f, v):
                missing.append(f)
        return (len(missing) > 0), missing

    # The remaining operators operate on a single field
    if not field:
        return False, []

    field_value = normalized_inputs.get(field, "")

    # Optional gating for not_contains_any
    if ttype == "not_contains_any" and trigger.get("evaluate_if_field_non_empty") is True:
        if not field_value:
            return False, []

    values = trigger.get("values", [])
    if not isinstance(values, list):
        values = []
    values_norm = [_norm_text(str(v)) for v in values if str(v).strip()]

    if ttype == "contains_any":
        matched = [v for v in values_norm if v and v in field_value]
        return (len(matched) > 0), matched

    if ttype == "equals_any":
        matched = [v for v in values_norm if v and field_value == v]
        return (len(matched) > 0), matched
        
    if ttype == "not_contains_any":
        # Match when NONE of the values appear in the field value.
        if not values_norm:
            return False, []
        matched = [v for v in values_norm if v and v in field_value]
        return (len(matched) == 0), []

    # Unknown trigger type
    return False, []


def _map_tier(total_score: int, risk_rules: dict) -> str:
    tiers = risk_rules.get("risk_tiers", []) if isinstance(risk_rules, dict) else []
    if not isinstance(tiers, list) or not tiers:
        # fallback
        if total_score >= 6:
            return "HIGH"
        if total_score >= 3:
            return "MEDIUM"
        return "LOW"

    matching = []
    for t in tiers:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id", "") or "").strip()
        try:
            mn = int(t.get("min_score"))
            mx = int(t.get("max_score"))
        except Exception:
            continue
        if mn <= total_score <= mx and tid:
            matching.append((mn, tid))

    if matching:
        # tie-breaker: highest min_score wins
        matching.sort(key=lambda x: (x[0], x[1]))
        return matching[-1][1]

    # If no match (config gap), choose closest by min_score
    best = None
    for t in tiers:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id", "") or "").strip()
        try:
            mn = int(t.get("min_score"))
        except Exception:
            continue
        if not tid:
            continue
        if best is None or mn > best[0]:
            best = (mn, tid)
    return best[1] if best else "LOW"


def _labels_for_ids(ids: list[str], catalog: dict, fallback_prefix: str = "") -> list[str]:
    out = []
    for _id in ids or []:
        _id = str(_id or "").strip()
        if not _id:
            continue
        label = None
        if isinstance(catalog, dict):
            entry = catalog.get(_id)
            if isinstance(entry, dict):
                label = entry.get("label")
        out.append(str(label).strip() if label else (fallback_prefix + _id))
    # de-dupe, preserve order
    seen = set()
    deduped = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped

def load_yaml_file(filepath):
    """Load and parse a YAML file, with mtime-based caching."""
    try:
        path = Path(filepath)
        # If file doesn't exist, behave like before.
        if not path.exists():
            return None

        key = str(path.resolve())
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = None

        cached = _YAML_CACHE.get(key)
        if isinstance(cached, dict) and cached.get("mtime") == mtime and "data" in cached:
            return cached.get("data")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        _YAML_CACHE[key] = {"mtime": mtime, "data": data}
        return data
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return None

def load_playbooks():
    """Load all investigation playbooks from the playbooks directory."""
    playbooks = {}
    if not PLAYBOOKS_DIR.exists():
        logger.warning("Playbooks directory not found")
        return playbooks
    
    for playbook_file in PLAYBOOKS_DIR.glob("*.yaml"):
        data = load_yaml_file(playbook_file)
        if data:
            playbooks[playbook_file.stem] = data
    return playbooks

def load_risk_rules():
    """Load risk assessment rules."""
    if not RISK_RULES_FILE.exists():
        logger.warning("Risk rules file not found")
        return {}
    return load_yaml_file(RISK_RULES_FILE) or {}

def load_disallowed_actions():
    """Load disallowed actions and red flags."""
    if not DISALLOWED_ACTIONS_FILE.exists():
        logger.warning("Disallowed actions file not found")
        return {}
    return load_yaml_file(DISALLOWED_ACTIONS_FILE) or {}

def load_report_template(investigation_type, audience):
    """Load a report template for the given investigation type and audience."""
    template_file = REPORT_TEMPLATES_DIR / f"{investigation_type}_{audience}.md"
    if not template_file.exists():
        template_file = REPORT_TEMPLATES_DIR / f"generic_{audience}.md"
    if not template_file.exists():
        template_file = REPORT_TEMPLATES_DIR / "default.md"
    
    if not template_file.exists():
        return "# Investigation Report Template\n\nTemplate not found. Please create appropriate report template files."
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error loading template: {e}")
        return f"Error loading template: {str(e)}"

# Reserved for the doctrine evaluator; not yet wired into scoring.
def load_jurisdiction_rules():
    """Load jurisdiction risk rules."""
    if not JURISDICTION_RULES_FILE.exists():
        logger.warning("Jurisdiction rules file not found")
        return {}
    return load_yaml_file(JURISDICTION_RULES_FILE) or {}

# Reserved for the doctrine evaluator; not yet wired into scoring.
def load_actor_profiles():
    """Load actor role profiles."""
    if not ACTOR_PROFILES_FILE.exists():
        logger.warning("Actor profiles file not found")
        return {}
    return load_yaml_file(ACTOR_PROFILES_FILE) or {}

# Reserved for the doctrine evaluator; not yet wired into scoring.
def load_method_classes():
    """Load method class definitions."""
    if not METHOD_CLASSES_FILE.exists():
        logger.warning("Method classes file not found")
        return {}
    return load_yaml_file(METHOD_CLASSES_FILE) or {}


def load_assigntools_catalog():
    """Load the AssignTools OSINT tool catalog YAML (tool directory)."""
    if not ASSIGNTOOLS_CATALOG_FILE.exists():
        logger.warning("AssignTools catalog file not found")
        return {"meta": {}, "categories": {}}
    return load_yaml_file(ASSIGNTOOLS_CATALOG_FILE) or {"meta": {}, "categories": {}}




def load_text_analyzer_doctrine():
    """Load TextAnalyzer doctrine YAML."""
    if not TEXT_ANALYZER_FILE.exists():
        logger.warning("Text analyzer doctrine file not found")
        return {}
    data = load_yaml_file(TEXT_ANALYZER_FILE)
    return data if isinstance(data, dict) else {}



def load_graph_builder_doctrine():
    """Load GraphBuilder doctrine YAML."""
    if not GRAPH_BUILDER_FILE.exists():
        logger.warning("Graph builder doctrine file not found")
        return {}
    data = load_yaml_file(GRAPH_BUILDER_FILE)
    return data if isinstance(data, dict) else {}


def load_report_redaction_doctrine():
    """Load ReportRedaction doctrine YAML."""
    if not REPORT_REDACTION_FILE.exists():
        logger.warning("Report redaction doctrine file not found")
        return {}
    data = load_yaml_file(REPORT_REDACTION_FILE)
    return data if isinstance(data, dict) else {}


def load_output_policy():
    """Load global output policy YAML."""
    if not OUTPUT_POLICY_FILE.exists():
        logger.warning("Output policy file not found")
        return {}
    data = load_yaml_file(OUTPUT_POLICY_FILE)
    return data if isinstance(data, dict) else {}


def get_tool_output_policy(tool_name: str) -> dict:
    """Return merged output policy for a tool: global limits + tool-specific overrides."""
    policy = load_output_policy()
    if not isinstance(policy, dict):
        policy = {}

    base = {}
    for section_name in ("style", "limits", "section_policy", "summary"):
        section = policy.get(section_name, {})
        if isinstance(section, dict):
            base.update(section)

    overrides = policy.get("tool_overrides", {})
    tool_policy = overrides.get(tool_name, {}) if isinstance(overrides, dict) else {}
    if isinstance(tool_policy, dict):
        base.update(tool_policy)

    return base


def _policy_int(policy: dict, key: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    """Read an integer policy value safely."""
    try:
        value = int(policy.get(key, default))
    except Exception:
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _clean_items(items) -> list[str]:
    """Normalize item lists for concise rendering."""
    if not items:
        return []
    out = []
    for item in items:
        text = str(item or "").strip()
        if text:
            out.append(text)
    return out


def limit_items(items, max_items: int) -> list[str]:
    """Limit a list while preserving order."""
    return _clean_items(items)[:max_items]


def render_bullets(items, max_items: int = 7) -> str:
    """Render a capped bullet list."""
    return "\n".join(f"- {item}" for item in limit_items(items, max_items))


def render_section(title: str, items, max_items: int = 7, omit_empty: bool = True) -> str:
    """Render a concise markdown section."""
    clean = limit_items(items, max_items)
    if omit_empty and not clean:
        return ""
    if not clean:
        clean = ["None identified."]
    return f"\n## {title}\n{render_bullets(clean, max_items)}"


def render_output_policy_block(tool_name: str) -> str:
    """Render presentation rules for the host LLM to apply when relaying a tool result.

    Deterministic tools build their output in Python, so the host model never sees
    the doctrine that governs presentation. Appending this block gives it the same
    policy the prompt-building tools embed directly.
    """
    merged = get_tool_output_policy(tool_name)
    if not merged:
        return ""

    policy = load_output_policy()
    if isinstance(policy, dict):
        order = policy.get("priority_order")
        if isinstance(order, list) and order and "priority_order" not in merged:
            merged = {**merged, "priority_order": order}

    try:
        policy_yaml = yaml.safe_dump(merged, sort_keys=False, allow_unicode=True).strip()
    except Exception:
        logger.warning(f"Could not serialize output policy for {tool_name}")
        return ""

    return f"""

---
📐 {tool_name.upper()} OUTPUT POLICY (applies to how you relay this result):
{policy_yaml}

- Follow this policy when presenting the result above.
- Content controls: do not drop findings, hard stops, or approvals to meet a limit.
- Do not add caveats, restatements, or commentary beyond what this result contains."""


def build_text_analyzer_prompt(text: str, investigator_language: str = "", constraints: str = "") -> str | None:
    """Build a doctrine-bound prompt for host-LLM TextAnalyzer execution."""
    doctrine = load_text_analyzer_doctrine()
    if not doctrine:
        return None

    output_policy = load_output_policy()
    text_policy = {}
    if isinstance(output_policy, dict):
        text_policy = (output_policy.get("tool_overrides", {}) or {}).get("TextAnalyzer", {}) or {}

    doctrine_yaml = yaml.safe_dump(doctrine, sort_keys=False, allow_unicode=True)
    output_policy_yaml = yaml.safe_dump(text_policy, sort_keys=False, allow_unicode=True) if text_policy else "{}"
    language = (investigator_language or "English").strip() or "English"
    constraints_text = (constraints or "").strip() or "[none provided]"

    return f"""You are TextAnalyzer, an OSINT text analysis tool operating under the Anakrisis doctrine.

Follow the doctrine below exactly. The doctrine defines what to highlight, how to interpret the text, what warnings to generate, what pivots to recommend, and the required output structure.

DOCTRINE YAML:
{doctrine_yaml}

TEXTANALYZER OUTPUT POLICY:
{output_policy_yaml}

Investigator response language: {language}
Operational constraints: {constraints_text}

Analyze the submitted text according to the doctrine.

Important requirements:
- Follow the doctrine response_structure section exactly and in order.
- Follow the TextAnalyzer output policy for brevity and bullet limits.
- If doctrine and output policy conflict, doctrine controls content; output policy controls brevity.
- Keep the response brief and investigator-focused.
- Do not redact PII or pivotable identifiers.
- Surface all detected high-value artifacts, even if the message appears benign.
- Include content warnings only when supported by the submitted text.
- Recommend only passive, OSINT-appropriate pivots.
- If translation is applicable, translate into the investigator response language.
- Do not add unrelated commentary outside the required structure.

SUBMITTED TEXT:
{text}
"""



def build_graph_builder_prompt(notes: str, case_context: str = "", investigator_language: str = "English") -> str | None:
    """Build a doctrine-bound prompt for host-LLM GraphBuilder execution."""
    doctrine = load_graph_builder_doctrine()
    if not doctrine:
        return None

    output_policy = load_output_policy()
    graph_policy = {}
    if isinstance(output_policy, dict):
        graph_policy = (output_policy.get("tool_overrides", {}) or {}).get("GraphBuilder", {}) or {}

    doctrine_yaml = yaml.safe_dump(doctrine, sort_keys=False, allow_unicode=True)
    output_policy_yaml = yaml.safe_dump(graph_policy, sort_keys=False, allow_unicode=True) if graph_policy else "{}"
    language = (investigator_language or "English").strip() or "English"
    context_text = (case_context or "").strip() or "[none provided]"

    return f"""You are GraphBuilder, an OSINT relationship-mapping tool operating under the Anakrisis doctrine.

Follow the doctrine below exactly. The doctrine defines entity/node types, relationship types, confidence levels, evidence requirements, graph rules, analyst observations, and the required output structure.

GRAPHBUILDER DOCTRINE YAML:
{doctrine_yaml}

GRAPHBUILDER OUTPUT POLICY:
{output_policy_yaml}

Investigator response language: {language}
Case context: {context_text}

Analyze the submitted investigative notes and convert them into a conservative relationship map.

Important requirements:
- Follow the doctrine response_structure section exactly and in order.
- Follow the GraphBuilder output policy for brevity and bullet limits.
- If doctrine and output policy conflict, doctrine controls content; output policy controls brevity.
- Separate facts from inferences.
- Do not equate correlation with attribution.
- Use conservative confidence levels.
- Include supporting evidence for each relationship.
- Flag relationships that require verification.
- Preserve relationship chains where they matter.
- Generate an Obsidian-compatible markdown graph note when requested by the doctrine.
- Do not add unrelated commentary outside the required structure.

SUBMITTED INVESTIGATIVE NOTES:
{notes}
"""


def build_report_redaction_prompt(
    report_text: str,
    audience: str = "public_release",
    redaction_notes: str = "",
    investigator_language: str = "English"
) -> str | None:
    """Build a doctrine-bound prompt for host-LLM ReportRedaction execution."""
    doctrine = load_report_redaction_doctrine()
    if not doctrine:
        return None

    output_policy = load_output_policy()
    redaction_policy = {}
    if isinstance(output_policy, dict):
        redaction_policy = (output_policy.get("tool_overrides", {}) or {}).get("ReportRedaction", {}) or {}

    doctrine_yaml = yaml.safe_dump(doctrine, sort_keys=False, allow_unicode=True)
    output_policy_yaml = yaml.safe_dump(redaction_policy, sort_keys=False, allow_unicode=True) if redaction_policy else "{}"
    language = (investigator_language or "English").strip() or "English"
    audience_text = (audience or "public_release").strip() or "public_release"
    notes_text = (redaction_notes or "").strip() or "[none provided]"

    return f"""You are ReportRedaction, an OSINT reporting and publication-safety tool operating under the Anakrisis doctrine.

Follow the doctrine below exactly. The doctrine defines redaction profiles, sensitive information categories, preservation rules, token rules, residual risk rules, and the required output structure.

REPORTREDACTION DOCTRINE YAML:
{doctrine_yaml}

REPORTREDACTION OUTPUT POLICY:
{output_policy_yaml}

Investigator response language: {language}
Selected audience / redaction profile: {audience_text}
Additional redaction notes: {notes_text}

Redact the submitted report according to the selected profile and doctrine.

Important requirements:
- Follow the doctrine response_structure section exactly and in order.
- Follow the ReportRedaction output policy for brevity and bullet limits.
- If doctrine and output policy conflict, doctrine controls redaction behavior; output policy controls brevity.
- Use structured replacement tokens instead of deleting sensitive material silently.
- Use consistent replacement tokens for repeated references to the same entity.
- Preserve analytical value and surrounding context wherever possible.
- Minimize unnecessary redactions.
- Include a redaction log with token, category, and reason.
- Include a residual risk assessment that notes re-identification risk from remaining context.
- Do not add unrelated commentary outside the required structure.

SUBMITTED REPORT TEXT:
{report_text}
"""

# === CASE WORKSPACE HELPERS ===

def _safe_case_dir(base: Path, case_name: str) -> Path:
    """Return a safe case directory under base. Reject path traversal and invalid names."""
    name = (case_name or "").strip()
    if not name or not _CASE_NAME_RE.match(name):
        raise ValueError("Invalid case name. Use letters/numbers/spaces/_/- (1–64 chars).")
    if "/" in name or "\\" in name or ".." in name:
        raise ValueError("Invalid case name.")
    # Normalize internal whitespace (optional, but keeps things tidy)
    name = " ".join(name.split())
    return base / name


def _ensure_case_scaffold(case_dir: Path, case_name: str) -> dict:
    """Create standard folders/files if missing. Idempotent."""
    created = {"dirs": [], "files": []}

    # Subdirectories
    for d in CASE_SUBDIRS:
        p = case_dir / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created["dirs"].append(str(p))

    # Files
    objective = case_dir / "objective.md"
    notes = case_dir / "notes.md"
    report = case_dir / "report.md"
    graph = case_dir / "graph.md"
    meta = case_dir / "metadata.json"

    if not objective.exists():
        objective.write_text(
            f"# Objective: {case_name}\n\n## Purpose\n\n## Scope\n\n## Constraints\n\n## Legal / Ethical Notes\n\n## Success Criteria\n",
            encoding="utf-8",
        )
        created["files"].append(str(objective))

    if not notes.exists():
        notes.write_text(
            f"# Notes: {case_name}\n\n## Intake\n\n## Leads\n\n## Observations\n\n## Open Questions\n",
            encoding="utf-8",
        )
        created["files"].append(str(notes))

    if not report.exists():
        report.write_text(
            f"# Report: {case_name}\n\n## Executive Summary\n\n## Methodology\n\n## Findings\n\n## Intelligence Assessment\n\n## Confidence Level\n\n## Sources\n\n## Limitations\n",
            encoding="utf-8",
        )
        created["files"].append(str(report))

    if not graph.exists():
        graph.write_text(
            f"# Graph: {case_name}\n\n## Entities\n\n## Relationships\n\n## Confidence Notes\n\n## Evidence\n\n## Verification Needed\n",
            encoding="utf-8",
        )
        created["files"].append(str(graph))

    if not meta.exists():
        meta.write_text(
            json.dumps(
                {
                    "case_name": case_name,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "status": "active",
                    "workshop_dir": str(CASES_DIR),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        created["files"].append(str(meta))

    return created

# === MCP TOOLS ===


@mcp.tool()
async def CreateCase(case_name: str = "", overwrite: bool = False) -> str:
    """Create a new investigation case workspace.

    Call this tool whenever the user asks to create/start/initialize a case, e.g.:
    - "Create case OperationXY"
    - "Start a new case called OperationXY"

    Creates: ~/anakrisis/cases/<case_name>/ with objective.md, notes.md, report.md, graph.md, metadata.json
    and subfolders: Sources, Screenshots, PDFs, Intelligence, OtherEvidence.

    If the case already exists, the call is refused unless overwrite=True, which
    re-runs the scaffold non-destructively: missing files and folders are created,
    existing content is never modified or deleted.
    """
    logger.info("Executing CreateCase")

    if not (case_name or "").strip():
        return "❌ Error: 'case_name' is required. Example: Create case Operation2"

    try:
        CASES_DIR.mkdir(parents=True, exist_ok=True)
        case_dir = _safe_case_dir(CASES_DIR, case_name)

        if case_dir.exists() and not overwrite:
            return f"⚠️ Case already exists: {case_dir}"

        case_dir.mkdir(parents=True, exist_ok=True)
        created = _ensure_case_scaffold(case_dir, case_name.strip())

        created_dirs = len(created.get("dirs", []))
        created_files = len(created.get("files", []))

        return (
            f"✅ Case ready: {case_dir}\n"
            f"- Created folders: {created_dirs}\n"
            f"- Created files: {created_files}\n"
            f"- Next: open objective.md and define scope, constraints, and success criteria."
            + render_output_policy_block("CreateCase")
        )

    except Exception as e:
        logger.error(f"Error in CreateCase: {e}")
        return f"❌ Error: {str(e)}"


# === RISK / SAFETY HELPERS ===

def classify_investigation(goal):
    """Classify investigation type based on goal."""
    
    goal_lower = (goal or "").lower()
    
    # Simple keyword-based classification
    classifications = []
    
    if "background" in goal_lower or "verify identity" in goal_lower:
        classifications.append("background_check")
    if "threat" in goal_lower or "harassment" in goal_lower or "safety" in goal_lower:
        classifications.append("threat_assessment")
    if "fraud" in goal_lower or "scam" in goal_lower:
        classifications.append("fraud_investigation")
    if "locate" in goal_lower or "find person" in goal_lower:
        classifications.append("person_location")
    if "digital footprint" in goal_lower or "social media" in goal_lower:
        classifications.append("digital_footprint_analysis")
    
    if not classifications:
        classifications.append("general_investigation")
    
    return classifications


def assess_risk(goal, what_you_have, constraints, actor_role="", method_class="", jurisdiction_country="", jurisdiction_state=""):
    """Assess risk using doctrine-driven rules from doctrine/risk_rules.yaml.

    actor_role, method_class, and jurisdiction_* are normalized into the inputs
    matched by doctrine triggers.

    Returns:
        (tier_id, factor_summaries, triggered_factor_ids, substantive_factor_ids)
    where tier_id is the doctrine tier id (e.g., TIER_LOW) when available, otherwise
    legacy LOW/MEDIUM/HIGH; triggered_factor_ids lists every fired factor; and
    substantive_factor_ids lists only action/intent signals (not missing-field
    factors) — this subset gates the quiet-by-default warning presentation.
    """
    risk_rules = load_risk_rules()
    if not isinstance(risk_rules, dict) or not risk_rules:
        # If doctrine missing, preserve old behavior via minimal fallback.
        goal_lower = (goal or "").lower()
        constraints_lower = (constraints or "").lower()
        risk_score = 0
        risk_factors = []
        fallback_triggered = []
        fallback_substantive = []
        if "authorization" not in constraints_lower and "consent" not in constraints_lower:
            risk_score += 1
            risk_factors.append("No explicit authorization or consent mentioned")
            # Missing-context signal: triggered, but not substantive on its own.
            fallback_triggered.append("fallback_missing_authorization")
        if "private individual" in constraints_lower or "civilian" in constraints_lower:
            risk_score += 2
            risk_factors.append("Target is a private individual (higher privacy expectations)")
            fallback_triggered.append("fallback_private_individual")
            fallback_substantive.append("fallback_private_individual")
        if "scrape" in goal_lower or "automate" in goal_lower or "bulk" in goal_lower:
            risk_score += 3
            risk_factors.append("Automation or bulk collection mentioned")
            fallback_triggered.append("fallback_automation_bulk")
            fallback_substantive.append("fallback_automation_bulk")
        return _map_tier(risk_score, {}), risk_factors, fallback_triggered, fallback_substantive

    # Normalize inputs per doctrine
    normalized_inputs = {
        "goal": _norm_text(goal),
        "what_you_have": _norm_text(what_you_have),
        "constraints": _norm_text(constraints),
        "actor_role": _norm_text(actor_role) or "unknown",
        "method_class": _norm_text(method_class) or "unknown",
        "jurisdiction_country": _norm_text(jurisdiction_country),
        "jurisdiction_state": _norm_text(jurisdiction_state),
    }

    factors = risk_rules.get("risk_factors", [])
    if not isinstance(factors, list):
        factors = []

    score_cap = 20
    score_floor = 0
    try:
        scoring_cfg = ((risk_rules.get("evaluation_model") or {}).get("scoring") or {})
        score_cap = int(scoring_cfg.get("score_cap", 20))
        score_floor = int(scoring_cfg.get("score_floor", 0))
    except Exception:
        score_cap = 20
        score_floor = 0

    total_score = 0
    triggered = []  # list of dicts

    for factor in factors:
        if not isinstance(factor, dict):
            continue
        fid = str(factor.get("id", "") or "").strip()
        fname = str(factor.get("name", "") or "").strip()
        fscore = factor.get("score", 0)
        try:
            fscore = int(fscore)
        except Exception:
            fscore = 0

        triggers = factor.get("triggers", [])
        if not isinstance(triggers, list) or not triggers:
            continue

        matched_any = False
        substantive_match = False  # matched by something other than missing_any
        match_explains = []

        for idx, trig in enumerate(triggers):
            matched, evidence = _trigger_matches(trig, normalized_inputs)
            if matched:
                matched_any = True
                if str(trig.get("type", "") or "").strip() != "missing_any":
                    substantive_match = True
                explain = str(trig.get("explain_text", "") or "").strip()
                if explain:
                    match_explains.append(explain)
                # capture minimal evidence tokens (not raw user text)
                if evidence:
                    match_explains.append("matched: " + ", ".join(str(x) for x in evidence))

        if matched_any:
            total_score += fscore

            # Prefer factor-level explanation (doctrine designs typically explain at factor level).
            # Fall back to description/rationale/name.
            factor_explain = str(
                factor.get("explain_text")
                or factor.get("description")
                or factor.get("rationale")
                or fname
                or fid
                or ""
            ).strip()

            # Append any matched trigger explain snippets/tokens (optional).
            explain_combined = factor_explain
            if match_explains:
                # Avoid duplicating identical strings
                extra = "; ".join(x for x in match_explains if x and x not in factor_explain)
                if extra:
                    explain_combined = f"{factor_explain} ({extra})" if factor_explain else extra

            triggered.append({
                "id": fid,
                "name": fname,
                "score": fscore,
                "explain": explain_combined if explain_combined else "triggered",
                "substantive": substantive_match,
            })

    if total_score > score_cap:
        total_score = score_cap
    if total_score < score_floor:
        total_score = score_floor

    tier_id = _map_tier(total_score, risk_rules)

    # Build user-facing factor summaries (stable, minimal)
    factor_summaries = []
    for t in triggered:
        nm = t.get("name") or t.get("id")
        sc = t.get("score")
        ex = t.get("explain")
        factor_summaries.append(f"{nm} (+{sc}): {ex}")

    # Attach score summary (useful for auditability)
    factor_summaries.insert(0, f"Total risk score: {total_score} (floor {score_floor}, cap {score_cap})")

    triggered_factor_ids = [t.get("id") for t in triggered if isinstance(t, dict) and t.get("id")]
    # Substantive = triggered by an actual action/intent signal, not merely by
    # missing optional planning fields. Used to gate quiet-by-default warnings.
    substantive_factor_ids = [
        t.get("id") for t in triggered
        if isinstance(t, dict) and t.get("id") and t.get("substantive")
    ]
    return tier_id, factor_summaries, triggered_factor_ids, substantive_factor_ids

def get_hard_stops(constraints: str):
    """Get list of explicitly disallowed actions.

    Back-compat behavior:
      - If disallowed_actions.yaml uses legacy lists (baseline_prohibited, passive_only_prohibited, unauthorized_prohibited),
        we include them using the previous simple heuristics.

    Doctrine-triggered behavior (preferred):
      - If disallowed_actions.yaml includes `rules:` as a list of dicts with `id/name/text` and `triggers:`,
        we evaluate triggers deterministically using the same trigger engine as risk factors.
        Rules may optionally include:
          - `text`: human-readable hard stop text
          - `applies_when`: optional gating like {"field_non_empty": "constraints"}
    """
    disallowed = load_disallowed_actions()
    if not isinstance(disallowed, dict):
        logger.warning("disallowed_actions.yaml did not load as a dict; treating as empty")
        disallowed = {}

    hard_stops: list[str] = []

    # --- Preferred: doctrine-triggered rules ---
    # Hard stops surface ONLY when the constraints text trips a rule trigger.
    # The legacy heuristic lists below are used solely as a fallback when no
    # deterministic `rules:` are defined, so a benign plan no longer dumps the
    # entire static prohibition list on every call (quiet-by-default model).
    rules = disallowed.get("rules", [])
    has_rules = isinstance(rules, list) and bool(rules)
    if has_rules:
        normalized_inputs = {
            "constraints": _norm_text(constraints),
        }

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            text = str(rule.get("text") or rule.get("name") or rule.get("id") or "").strip()
            if not text:
                continue

            triggers = rule.get("triggers", [])
            if not isinstance(triggers, list) or not triggers:
                continue

            matched_any = False
            for trig in triggers:
                matched, _evidence = _trigger_matches(trig, normalized_inputs)
                if matched:
                    matched_any = True
                    break

            if matched_any:
                hard_stops.append(text)

    # --- Back-compat: legacy heuristic lists (only when no `rules:` defined) ---
    if not has_rules:
        constraints_lower = (constraints or "").lower()

        if "baseline_prohibited" in disallowed:
            value = disallowed.get("baseline_prohibited", [])
            if isinstance(value, list):
                hard_stops.extend([str(x) for x in value if str(x).strip()])

        if "passive" in constraints_lower or "passive-only" in constraints_lower:
            if "passive_only_prohibited" in disallowed:
                value = disallowed.get("passive_only_prohibited", [])
                if isinstance(value, list):
                    hard_stops.extend([str(x) for x in value if str(x).strip()])

        if "authorization" not in constraints_lower and "consent" not in constraints_lower:
            if "unauthorized_prohibited" in disallowed:
                value = disallowed.get("unauthorized_prohibited", [])
                if isinstance(value, list):
                    hard_stops.extend([str(x) for x in value if str(x).strip()])

    # De-dupe, preserve order
    seen = set()
    out = []
    for x in hard_stops:
        x = str(x).strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out

def get_safe_first_steps(investigation_types):
    """Get safe first steps based on investigation type."""
    playbooks = load_playbooks()
    steps = []
    
    for inv_type in investigation_types:
        if inv_type in playbooks:
            playbook = playbooks.get(inv_type)
            if isinstance(playbook, dict):
                sfs = playbook.get("safe_first_steps", [])
                if isinstance(sfs, list):
                    steps.extend(sfs)
    
    if not steps:
        steps = [
            "Document investigation scope and objectives",
            "Review applicable policies and legal constraints",
            "Identify publicly available information sources",
            "Establish documentation and chain-of-custody procedures"
        ]
    
    seen = set()
    out = []
    for x in steps:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

VALID_RISK_CATEGORIES = ("tos_risk", "privacy_risk", "legal_risk", "operational_risk")


def _action_rule_matches(rule: dict, haystack: str) -> str | None:
    """Evaluate one action rule against text. Returns the matched phrase, or None.

    Supports two trigger types:
      contains_any -- any listed phrase appears as a substring
      all_of       -- every listed token appears somewhere, in any order.
                      Needed because literal phrase matching breaks the moment a
                      user writes "fake Instagram account" instead of "fake account".
    """
    triggers = rule.get("triggers", [])
    if not isinstance(triggers, list):
        return None

    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        values = trigger.get("values", [])
        if not isinstance(values, list) or not values:
            continue
        ttype = str(trigger.get("type", "contains_any")).strip()
        tokens = [str(v).lower().strip() for v in values if str(v).strip()]

        if ttype == "all_of":
            if tokens and all(tok in haystack for tok in tokens):
                return " + ".join(tokens)
        else:
            for tok in tokens:
                if tok in haystack:
                    return tok
    return None


def check_action_safety(proposed_action, context):
    """Check a proposed action against doctrine action rules.

    Returns (warnings, hard_stops, matched_any):
      warnings    -- dict of category -> list of warning strings
      hard_stops  -- list of prohibited-action strings that matched
      matched_any -- whether ANY rule fired

    matched_any is returned separately so the caller can distinguish
    "reviewed and clean" from "nothing in the ruleset recognized this".
    Those are not the same result and must not render the same way.
    """
    warnings = {cat: [] for cat in VALID_RISK_CATEGORIES}
    hard_stops: list[str] = []

    action_lower = (proposed_action or "").lower()
    context_lower = (context or "").lower()
    haystack = f"{action_lower}\n{context_lower}"

    disallowed = load_disallowed_actions()
    if not isinstance(disallowed, dict):
        logger.warning("disallowed_actions.yaml did not load as a dict; action rules unavailable")
        disallowed = {}

    action_rules = disallowed.get("action_rules", [])
    if not isinstance(action_rules, list) or not action_rules:
        logger.warning("No action_rules found in disallowed_actions.yaml; RulesOfEngagement is running blind")
        action_rules = []

    for rule in action_rules:
        if not isinstance(rule, dict):
            continue
        matched = _action_rule_matches(rule, haystack)
        if not matched:
            continue

        text = str(rule.get("text") or rule.get("id") or "Disallowed action").strip()
        severity = str(rule.get("severity", "elevated")).strip().lower()
        category = str(rule.get("category", "privacy_risk")).strip()
        if category not in warnings:
            category = "privacy_risk"

        warnings[category].append(f"{text} (matched: {matched})")
        if severity == "hard_stop":
            hard_stops.append(text)

    matched_any = bool(hard_stops) or any(warnings[c] for c in warnings)
    return warnings, hard_stops, matched_any

def get_safer_alternatives(proposed_action):
    """Suggest safer alternatives to risky actions."""
    alternatives = []
    action_lower = (proposed_action or "").lower()
    
    if "scrape" in action_lower or "crawl" in action_lower:
        alternatives.append("Use official APIs where available")
        alternatives.append("Manual review of publicly accessible pages")
        alternatives.append("Use commercial OSINT platforms with proper licensing")
    
    if "login" in action_lower or "access account" in action_lower:
        alternatives.append("Work with platform's legal/LEA channels")
        alternatives.append("Use lawful subpoena or court order processes")
        alternatives.append("Rely on publicly visible information only")
    
    if "automate" in action_lower or "bulk" in action_lower:
        alternatives.append("Manual, targeted collection within rate limits")
        alternatives.append("Use platforms with terms allowing research access")
        alternatives.append("Partner with academic or commercial providers")

    # Impersonating a real person, or pretexting, stays prohibited -- redirect to lawful routes.
    if any(k in action_lower for k in ("impersonate", "pose as", "pretend to be", "catfish",
                                       "false identity", "identity theft", "pretext")):
        alternatives.append("Use a non-attributable research persona instead -- invent an identity rather than borrowing a real person's")
        alternatives.append("Request the material through discovery or a records request")
        alternatives.append("Build the record from dated public activity across independent sources")

    # Research personas are permitted for viewing, so steer the *how*, not the whether.
    if any(k in action_lower for k in ("sock puppet", "sockpuppet", "burner", "throwaway",
                                       "research persona", "research account", "alt account",
                                       "fake account", "fake profile", "dummy account")):
        alternatives.append("Keep the persona non-attributable: no real person's name, photo, or biography, and nothing traceable to you")
        alternatives.append("View only -- no follows, requests, messages, comments, reactions, or story views")
        alternatives.append("Heads up: some platforms' terms don't allow secondary accounts -- just keep it in mind")
        alternatives.append("Remember a persona does not unlock private content -- reaching it still needs a follow request, which is interaction")

    if any(k in action_lower for k in ("follow request", "friend request", "connection request",
                                       "message", "contact", "reach out")):
        alternatives.append("Do not initiate contact; route any approach through counsel of record")
        alternatives.append("Rely on content visible without interaction, and log the visibility state")

    if any(k in action_lower for k in ("private post", "private account", "private profile",
                                       "restricted content", "non-public")):
        alternatives.append("Use lawful process — subpoena, discovery request, or platform legal channel")
        alternatives.append("Document that the content was restricted and not accessed")

    if not alternatives:
        alternatives.append("Consult with legal counsel before proceeding")
        alternatives.append("Use passive collection methods only")
        alternatives.append("Limit scope to publicly accessible information")
    
    return alternatives

# === MCP TOOLS (continued) ===

@mcp.tool()
async def MissionBrief(
    goal: str = "",
    what_you_have: str = "",
    constraints: str = "",
    actor_role: str = "",
    method_class: str = "",
    jurisdiction_country: str = "",
    jurisdiction_state: str = ""
) -> str:
    """Pre-investigation planning, classification, and safety assessment tool."""
    logger.info("Executing MissionBrief")
    
    if not goal.strip():
        return "❌ Error: 'goal' parameter is required. Please describe what you're trying to accomplish."
    
    
    try:
        output_policy = get_tool_output_policy("MissionBrief")
        max_items = _policy_int(output_policy, "max_bullets_per_section", 7, maximum=12)

        # Classify investigation
        investigation_types = classify_investigation(goal)
        
        # Assess risk
        risk_tier, risk_factors, triggered_factor_ids, substantive_factor_ids = assess_risk(
            goal, what_you_have, constraints,
            actor_role=actor_role, method_class=method_class,
            jurisdiction_country=jurisdiction_country, jurisdiction_state=jurisdiction_state
        )
        
        # Get hard stops
        hard_stops = get_hard_stops(constraints)
        
        # Get safe first steps
        safe_steps = get_safe_first_steps(investigation_types)

        # Passive collection implied by the artifacts in hand, phrased for whatever
        # is driving this session (see collection_mode()). Suppressed on a hard stop.
        collection_suggestions = suggest_collection(what_you_have, hard_stops)
        
        # Determine required approvals / controls from doctrine
        risk_rules = load_risk_rules()
        approvals_needed = []
        mandatory_controls = []
        mitigations_recommended = []
        response_mode = "normal"

        if isinstance(risk_rules, dict) and risk_rules:
            tiers = risk_rules.get("risk_tiers", []) if isinstance(risk_rules.get("risk_tiers", []), list) else []
            tier_cfg = None
            for t in tiers:
                if isinstance(t, dict) and str(t.get("id", "")).strip() == str(risk_tier).strip():
                    tier_cfg = t
                    break

            catalogs = risk_rules.get("catalogs", {}) if isinstance(risk_rules.get("catalogs", {}), dict) else {}
            approvals_catalog = catalogs.get("approvals", {}) if isinstance(catalogs.get("approvals", {}), dict) else {}
            controls_catalog = catalogs.get("controls", {}) if isinstance(catalogs.get("controls", {}), dict) else {}

            # Tier-level requirements
            if isinstance(tier_cfg, dict):
                response_mode = str(tier_cfg.get("response_mode", "normal") or "normal").strip()
                tier_approvals = tier_cfg.get("required_approvals", []) if isinstance(tier_cfg.get("required_approvals", []), list) else []
                tier_controls = tier_cfg.get("mandatory_controls", []) if isinstance(tier_cfg.get("mandatory_controls", []), list) else []

                approvals_needed = _labels_for_ids(tier_approvals, approvals_catalog)
                mandatory_controls = _labels_for_ids(tier_controls, controls_catalog)

            # Factor-level mitigations
            mitigations = risk_rules.get("mitigations", {}) if isinstance(risk_rules.get("mitigations", {}), dict) else {}
            by_factor = mitigations.get("by_factor_id", {}) if isinstance(mitigations.get("by_factor_id", {}), dict) else {}

            factor_control_ids = []
            factor_actions = []
            for fid in (triggered_factor_ids or []):
                cfg = by_factor.get(fid)
                if not isinstance(cfg, dict):
                    continue

                mc = cfg.get("mandatory_controls", [])
                if isinstance(mc, list):
                    factor_control_ids.extend([str(x or "").strip() for x in mc if str(x or "").strip()])

                acts = cfg.get("actions", [])
                if isinstance(acts, list):
                    factor_actions.extend([str(x or "").strip() for x in acts if str(x or "").strip()])

            # Union tier controls + factor controls, using catalog labels when available
            factor_controls_labeled = _labels_for_ids(factor_control_ids, controls_catalog)
            mandatory_controls = list(dict.fromkeys((mandatory_controls or []) + factor_controls_labeled))

            # De-dupe mitigations actions
            mitigations_recommended = list(dict.fromkeys(factor_actions))

        # Fallback messaging if doctrine missing
        if not approvals_needed and str(risk_tier) in {"HIGH", "MEDIUM"}:
            if str(risk_tier) == "HIGH":
                approvals_needed = ["Legal/Compliance review", "Supervisor approval"]
            elif str(risk_tier) == "MEDIUM":
                approvals_needed = ["Supervisor approval"]
        
        # Quiet by default: only surface warnings, hard stops, approvals,
        # controls, mitigations, and the audit checklist when the user actually
        # trips a substantive risk factor (action/intent signal) or a hard stop.
        # Missing optional planning fields alone do NOT trigger warnings.
        triggered = bool(substantive_factor_ids) or bool(hard_stops)

        # Build concise response
        key_findings = [
            f"Classification: {', '.join(investigation_types)}",
        ]
        if triggered:
            key_findings.append(f"Risk tier: {risk_tier}")
            key_findings.append(f"Response mode: {response_mode}")
            if triggered_factor_ids:
                key_findings.append(f"Triggered risk factors: {len(triggered_factor_ids)}")
            if hard_stops:
                key_findings.append(f"Hard stops identified: {len(hard_stops)}")

        response_parts = [
            "📋 INVESTIGATION PRE-FLIGHT ASSESSMENT",
            render_section("Key Findings", key_findings, max_items),
            render_section("Safe Next Steps", safe_steps, max_items),
            render_collection_offer(collection_suggestions),
        ]

        if triggered:
            response_parts.extend([
                render_section("Risk Factors", risk_factors, max_items),
                render_section("Hard Stops", hard_stops, max_items),
                render_section("Required Approvals", approvals_needed, max_items),
                render_section("Mandatory Controls", mandatory_controls, max_items),
                render_section("Mitigations", mitigations_recommended, max_items),
                render_section("Audit Checklist", [
                    "Document scope, authority, and constraints.",
                    "Record sources, timestamps, and collection methods.",
                    "Preserve original artifacts where possible.",
                    "Separate facts from inferences.",
                    "Reassess before escalating collection methods.",
                ], max_items),
            ])

        response = "\n".join(part for part in response_parts if part)

        # --- Follow-up questions (deterministic, privacy-first) ---
        followups = []

        # Jurisdiction narrowing
        jc = (jurisdiction_country or "").strip()
        js = (jurisdiction_state or "").strip()
        jc_lower = jc.lower()

        if not jc:
            followups.append("What is the primary jurisdiction involved? (country only, e.g., United States)")
        else:
            us_aliases = ["united states", "usa", "us", "u.s.", "u.s.a."]
            if jc_lower in us_aliases and not js:
                followups.append("Which U.S. state is most relevant (subject location, data location, or investigator location)?")

        # Actor role
        if not (actor_role or "").strip():
            followups.append("What is your actor role? (e.g., private_individual, licensed_investigator, journalist, academic_researcher, corporate_security, ngo_humanitarian)")

        # Method class
        if not (method_class or "").strip():
            followups.append("What method class will you use? (passive_only / passive_plus / active / unknown)")

        if triggered and followups:
            response += "\n\n🔎 Follow-up (to narrow legal/risk guidance):\n" + "\n".join(f"- {q}" for q in followups)

        response += render_output_policy_block("MissionBrief")
        return response

    except Exception as e:
        logger.error(f"Error in MissionBrief: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def CourseCorrection(current_phase: str = "", new_artifacts: str = "", constraints: str = "") -> str:
    """Update planning after progress, leads, or roadblocks in investigation."""
    logger.info("Executing CourseCorrection")
    
    if not current_phase.strip():
        return "❌ Error: 'current_phase' parameter is required. Valid phases: intake, planning, discovery, validation, reporting"
    
    valid_phases = ["intake", "planning", "discovery", "validation", "reporting"]
    if current_phase.lower() not in valid_phases:
        return f"❌ Error: Invalid phase. Must be one of: {', '.join(valid_phases)}"
    
    
    try:
        output_policy = get_tool_output_policy("CourseCorrection")
        max_items = _policy_int(output_policy, "max_bullets_per_section", 5, maximum=10)
        # Phase-specific guidance
        phase_guidance = {
            "intake": [
                "Clarify investigation scope and objectives",
                "Identify all legal and ethical constraints",
                "Determine authorization and consent requirements",
                "Establish success criteria and boundaries"
            ],
            "planning": [
                "Map available passive information sources",
                "Identify required approvals for each source",
                "Create collection timeline and priorities",
                "Establish documentation procedures"
            ],
            "discovery": [
                "Collect information from approved sources aligned with authorization and constraints",
                "Document source, timestamp, and method for each artifact",
                "Continuously assess whether to continue or escalate",
                "Flag any unexpected findings for review"
            ],
            "validation": [
                "Cross-reference findings across multiple independent sources",
                "Document confidence levels for each finding",
                "Identify gaps and uncertainties",
                "Avoid confirmation bias - seek contradictory information"
            ],
            "reporting": [
                "Use appropriate report template for audience",
                "Clearly separate facts from inferences",
                "Document methodology and limitations",
                "Include what was NOT found and why"
            ]
        }
        
        current_guidance = phase_guidance.get(current_phase.lower(), [])
        
        # Re-assess risk with new artifacts
        risk_tier, risk_factors, cc_triggered_ids, cc_substantive_ids = assess_risk("", new_artifacts, constraints)

        # Escalation warnings
        escalation_warning = ""
        artifacts_lower = (new_artifacts or "").lower()
        if any(word in artifacts_lower for word in ["identified person", "real name", "location", "address", "employer"]):
            escalation_warning = "\n⚠️  ESCALATION ALERT: New artifacts involve personal identifiers. Heightened privacy and ethical considerations apply.\n"

        # What to avoid next
        avoid_next = get_hard_stops(constraints)

        # Quiet by default: phase guidance always shows, but risk factors, hard
        # stops, and the pre-phase checklist only surface when a risk factor,
        # hard stop, or escalation keyword actually fires.
        triggered = bool(cc_substantive_ids) or bool(avoid_next) or bool(escalation_warning)

        key_findings = [
            f"Phase: {current_phase.lower()}",
        ]
        if triggered:
            key_findings.append(f"Updated risk tier: {risk_tier}")
            if escalation_warning:
                key_findings.append("Escalation alert: personal identifiers detected in new artifacts.")

        response_parts = [
            "📍 COURSE CORRECTION",
            render_section("Key Findings", key_findings, max_items),
            render_section("Phase Actions", current_guidance, max_items),
        ]
        if triggered:
            response_parts.extend([
                render_section("Risk Factors", risk_factors, max_items),
                render_section("Avoid Next", avoid_next, max_items),
                render_section("Before Next Phase", [
                    "Confirm current phase objectives are met.",
                    "Update risk assessment if scope changed.",
                    "Confirm continued authorization.",
                    "Document what changed and why.",
                ], max_items),
            ])
        response = "\n".join(part for part in response_parts if part)
        response += render_output_policy_block("CourseCorrection")
        return response

    except Exception as e:
        logger.error(f"Error in CourseCorrection: {e}")
        return f"❌ Error: {str(e)}"


# === TEXT ANALYZER TOOL ===


@mcp.tool()
async def TextAnalyzer(
    text: str = "",
    investigator_language: str = "English",
    constraints: str = ""
) -> str:
    """Build a doctrine-bound prompt for OSINT text analysis using doctrine/text_analyzer.yaml."""
    logger.info("Executing TextAnalyzer")

    if not (text or "").strip():
        return "❌ Error: 'text' parameter is required. Paste the message or text to analyze."

    prompt = build_text_analyzer_prompt(text, investigator_language, constraints)
    if prompt is None:
        return "❌ Error: doctrine/text_analyzer.yaml is missing or invalid."

    return f"""🧠 TEXT ANALYZER

Use the following doctrine-bound prompt to analyze the submitted text with the host LLM:

---

{prompt}
"""

# === GRAPH BUILDER TOOL ===


@mcp.tool()
async def GraphBuilder(
    notes: str = "",
    case_context: str = "",
    investigator_language: str = "English"
) -> str:
    """Build a doctrine-bound prompt for OSINT relationship mapping using doctrine/graph_builder.yaml."""
    logger.info("Executing GraphBuilder")

    if not (notes or "").strip():
        return "❌ Error: 'notes' parameter is required. Paste investigative notes, artifacts, or findings to map."

    prompt = build_graph_builder_prompt(notes, case_context, investigator_language)
    if prompt is None:
        return "❌ Error: doctrine/graph_builder.yaml is missing or invalid."

    return f"""🕸️ GRAPH BUILDER

Use the following doctrine-bound prompt to map entities and relationships with the host LLM:

---

{prompt}
"""

# === REPORT REDACTION TOOL ===

@mcp.tool()
async def ReportRedaction(
    report_text: str = "",
    audience: str = "public_release",
    redaction_notes: str = "",
    investigator_language: str = "English"
) -> str:
    """Build a doctrine-bound prompt for report redaction using doctrine/report_redaction.yaml."""
    logger.info("Executing ReportRedaction")

    if not (report_text or "").strip():
        return "❌ Error: 'report_text' parameter is required. Paste the report or excerpt to redact."

    prompt = build_report_redaction_prompt(report_text, audience, redaction_notes, investigator_language)
    if prompt is None:
        return "❌ Error: doctrine/report_redaction.yaml is missing or invalid."

    return f"""🧾 REPORT REDACTION

Use the following doctrine-bound prompt to redact the submitted report with the host LLM:

---

{prompt}
"""

@mcp.tool()
async def RulesOfEngagement(proposed_action: str = "", context: str = "") -> str:
    """Safety interlock for proposed actions - identifies risks and suggests safer alternatives."""
    logger.info("Executing RulesOfEngagement")
    
    if not proposed_action.strip():
        return "❌ Error: 'proposed_action' parameter is required. Describe what you're considering doing."
    
    try:
        output_policy = get_tool_output_policy("RulesOfEngagement")
        max_items = _policy_int(output_policy, "max_bullets_per_section", 6, maximum=10)
        # Check action safety
        warnings, hard_stops, matched_any = check_action_safety(proposed_action, context)

        total_warnings = sum(len(w) for w in warnings.values())

        # No rule fired. This is NOT a clearance -- the ruleset is finite and an
        # unrecognized action is unassessed, not safe. Say so plainly.
        if not matched_any:
            return "\n".join(part for part in [
                "🔍 ACTION REVIEW",
                render_section("Key Findings", [
                    "Safety level: ⚪ No rule matched — NOT a clearance.",
                    "No doctrine action rule recognized this description. Unassessed is not the same as safe.",
                    "Confirm the action is passive, authorized, and within scope before proceeding.",
                    "If the action involves a target individual, restate it plainly and re-run this check.",
                ], max_items),
            ] if part) + render_output_policy_block("RulesOfEngagement")

        alternatives = get_safer_alternatives(proposed_action)

        if hard_stops:
            safety_level = "🛑 PROHIBITED - HARD STOP"
            recommendation = "This action is disallowed by doctrine. Do not proceed. No authorization level clears a hard stop."
        elif total_warnings >= 3:
            safety_level = "🛑 HIGH RISK - REVIEW REQUIRED"
            recommendation = "This action requires review and authorization. Consider appropriate oversight."
        else:
            safety_level = "⚠️  ELEVATED RISK - PROCEED WITH CAUTION"
            recommendation = "This action requires explicit authorization and careful execution. Consider safer alternatives first."

        warning_items = []
        for category, values in warnings.items():
            label = category.replace("_", " ").title()
            for warning in values:
                warning_items.append(f"{label}: {warning}")

        header = "🛑 ACTION PROHIBITED" if hard_stops else "🚨 ACTION SAFETY ASSESSMENT"
        response_parts = [
            header,
            render_section("Key Findings", [
                f"Safety level: {safety_level}",
                recommendation,
            ], max_items),
            render_section("Hard Stops", hard_stops, max_items),
            render_section("Warnings", warning_items, max_items),
            render_section("Safer Alternatives", alternatives, max_items),
            render_section(
                "Do Not Proceed" if hard_stops else "Before Proceeding",
                [
                    "A hard stop cannot be cleared by authorization or supervisor approval.",
                    "Log the request and the refusal in the case record.",
                    "Re-scope to a lawful alternative above, then re-run this check.",
                ] if hard_stops else [
                    "Verify explicit authorization.",
                    "Review applicable Terms of Service.",
                    "Use the least invasive method available.",
                    "Document legal basis and oversight.",
                ],
                max_items,
            ),
        ]
        response = "\n".join(part for part in response_parts if part)
        response += render_output_policy_block("RulesOfEngagement")
        return response
    except Exception as e:
        logger.error(f"Error in RulesOfEngagement: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def ReportTemplate(investigation_type: str = "", audience: str = "", constraints: str = "") -> str:
    """Generate documentation template based on investigation type and audience."""
    logger.info("Executing ReportTemplate")
    
    if not investigation_type.strip():
        investigation_type = "general_investigation"
    
    if not audience.strip():
        audience = "internal"
    
    try:
        # Load appropriate template
        template = load_report_template(investigation_type, audience)
        
        # Add metadata header
        response = f"""📄 INVESTIGATION REPORT TEMPLATE

Investigation Type: {investigation_type}
Audience: {audience}
Generated: [Insert Date/Time]

⚠️  INSTRUCTIONS:
- Fill in all sections marked with [PLACEHOLDER]
- Remove sections not applicable to your investigation
- Never include information you cannot verify
- Clearly distinguish facts from inferences
- Document what was NOT found
- Include confidence levels for all findings

---

{template}

---

💡 Template Notes:
- This is a structure only - you must fill in actual investigation details
- Adapt sections as needed for your specific case
- Always include methodology and limitations sections
- Document chain of custody for all evidence
- Have report reviewed before distribution
"""

        response += render_output_policy_block("ReportTemplate")
        return response

    except Exception as e:
        logger.error(f"Error in ReportTemplate: {e}")
        return f"❌ Error: {str(e)}"

@mcp.tool()
async def AssignTools(
    artifact_type: str = "",
    goal: str = "",
    constraints: str = "",
    max_results: int = 0
) -> str:
    """
    Tool recommender. Suggests external OSINT tools from a local YAML catalog.
    """
    logger.info("Executing AssignTools")
    output_policy = get_tool_output_policy("AssignTools")
    policy_max_results = _policy_int(output_policy, "max_results", 15, maximum=30)
    max_per_category = _policy_int(output_policy, "max_results_per_category", 8, maximum=20)
    group_by_category = bool(output_policy.get("group_by_category", True))

    catalog = load_assigntools_catalog()
    catalog = catalog if isinstance(catalog, dict) else {}
    categories = catalog.get("categories", {}) if isinstance(catalog.get("categories", {}), dict) else {}

    if not categories:
        return "❌ Error: AssignTools catalog is empty or missing categories. Ensure doctrine/assigntools.yaml exists and has a 'categories:' section."

    # Normalize inputs
    artifact = (artifact_type or "").strip().lower()
    query_text = f"{goal} {constraints}".strip().lower()


    # Map common synonyms to catalog category keys (must match assigntools.yaml category ids)
    synonym_map = {
        # Username
        "username": "username",
        "handle": "username",
        "user": "username",
        "screenname": "username",
        "nickname": "username",
        "alias": "username",
        "account": "username",
        "profile": "username",

        # Email
        "email": "email",
        "mail": "email",
        "e-mail": "email",
        "email address": "email",

        # Phone
        "phone": "phone",
        "phone number": "phone",
        "number": "phone",
        "mobile": "phone",
        "cell": "phone",

        # Companies / Organizations
        "company": "companies",
        "business": "companies",
        "organization": "companies",
        "org": "companies",
        "corporation": "companies",
        "employer": "companies",

        # Company registries
        "registry": "company_registries",
        "business registry": "company_registries",
        "corporate registry": "company_registries",

        # DNS / WHOIS / Internet infrastructure
        "dns": "dns",
        "whois": "whois",
        "domain": "internet_scan",
        "website": "internet_scan",
        "ip": "internet_scan",
        "ip address": "internet_scan",
        "hostname": "internet_scan",
        "server": "internet_scan",
        "infrastructure": "internet_scan",

        # People
        "name": "people_records",
        "person": "people_records",
        "individual": "people_records",
        "identity": "people_records",
        "real name": "people_records",

        # Geospatial
        "map": "geospatial_intelligence",
        "location": "geospatial_intelligence",
        "coordinates": "geospatial_intelligence",
        "geolocation": "geospatial_intelligence",
        "geo": "geospatial_intelligence",

        # Search engines
        "search": "search",
        "google search": "search",
        "bing": "search",
        "duckduckgo": "search",

        # Image search
        "image": "image_search",
        "photo": "image_search",
        "picture": "image_search",
        "reverse image": "image_search",
        "facial recognition": "image_search",

        # Social media
        "social": "social_media",
        "social media": "social_media",
        "facebook": "social_media",
        "instagram": "social_media",
        "twitter": "social_media",
        "x": "social_media",
        "linkedin": "social_media",
        "reddit": "social_media",
        "tiktok": "social_media",
        "pinterest": "social_media",

        # Google dorking
        "dork": "google_dork",
        "google dork": "google_dork",
        "advanced search": "google_dork",

        # Safety / malware
        "malware": "safety",
        "virus": "safety",
        "reputation": "safety",
        "threat": "safety",

        # OSINT directories
        "osint tools": "osint_directories",
        "osint directory": "osint_directories",
        "osint framework": "osint_directories",

        # Vehicles
        "vin": "vehicles",
        "license plate": "vehicles",
        "vehicle": "vehicles",
        "car": "vehicles",

        # Cryptocurrency
        "crypto": "cryptocurrency",
        "cryptocurrency": "cryptocurrency",
        "bitcoin": "cryptocurrency",
        "ethereum": "cryptocurrency",
        "wallet": "cryptocurrency",
        "blockchain": "cryptocurrency",

        # Documents / metadata
        "metadata": "documents_metadata",
        "document": "documents_metadata",
        "pdf": "documents_metadata",
        "docx": "documents_metadata",
        "file analysis": "documents_metadata",
    }
    if artifact in synonym_map:
        artifact = synonym_map[artifact]

    # Flatten catalog into list of tool dicts with category metadata
    flattened = []
    for cat_key, cat_data in categories.items():
        tools = (cat_data or {}).get("tools", []) or []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            flattened.append({
                "category_key": cat_key,
                "category_label": (cat_data or {}).get("label", cat_key),
                "tool": tool
            })

    if not flattened:
        return "❌ Error: No tools found in catalog. Add tools under categories: <category>: tools: - id: ..."

    # Candidate filtering:
    # If artifact_type provided and matches a category key, prioritize those tools.
    # If artifact_type is empty/unknown, consider all tools.
    artifact_matches_category = artifact and artifact in categories

    def score_item(item: dict) -> int:
        tool = item["tool"]
        cat_key = item["category_key"]

        name = str(tool.get("name", "")).lower()
        desc = str(tool.get("description", "")).lower()
        tags = tool.get("tags", []) or []
        tags_text = " ".join([str(t).lower() for t in tags])

        s = 0

        # Category boost if artifact matches
        if artifact_matches_category:
            if cat_key == artifact:
                s += 50
            else:
                s -= 10

        # Keyword overlap scoring (simple, robust)
        for token in set(query_text.split()):
            if len(token) < 3:
                continue
            if token in name:
                s += 6
            if token in tags_text:
                s += 5
            if token in desc:
                s += 3

        # Small boosts for “quality” metadata if present
        cost = str(tool.get("cost", "")).lower()
        if cost == "free":
            s += 1

        # Tools tagged "pivot" (multi-input pivoting) get a small boost
        if "pivot" in tags_text:
            s += 1

        return s

    ranked = sorted(flattened, key=score_item, reverse=True)

    # If artifact_type provided but not a known category, we still return best matches across catalog
    # but we tell the user which categories exist.
    available_categories = ", ".join(sorted(categories.keys()))

    # Clamp max_results using output policy as the default ceiling.
    try:
        requested_max_results = int(max_results)
    except Exception:
        requested_max_results = policy_max_results
    if requested_max_results <= 0:
        requested_max_results = policy_max_results
    max_results = max(1, min(requested_max_results, policy_max_results))

    top = ranked[:max_results]

    # Build response
    header = f"""
🧭 ASSIGNTOOLS — OSINT Tool Recommendations

Artifact Type: {artifact_type or "unspecified"}
Goal: {goal or "[not provided]"}
Constraints: {constraints or "[not provided]"}

Note: This tool only recommends external resources from a local catalog.
"""

    if artifact and not artifact_matches_category:
        header += f"\nℹ️  Unknown artifact_type '{artifact_type}'. Available categories: {available_categories}\n"

    lines = [header, "⭐ Top Recommendations:"]

    def _tool_summary_line(item: dict, idx: int | None = None) -> list[str]:
        tool = item["tool"]
        tool_name = tool.get("name", tool.get("id", "unknown"))
        tool_id = tool.get("id", "unknown")
        url = tool.get("url", "")
        desc = tool.get("description", "")
        cost = tool.get("cost", "")
        account_required = str(tool.get("account_required", "Unknown")).strip()

        meta_bits = []
        if cost:
            meta_bits.append(f"cost={cost}")
        if account_required:
            meta_bits.append(f"account_required={account_required}")
        meta_str = f" ({', '.join(meta_bits)})" if meta_bits else ""

        prefix = f"{idx}. " if idx is not None else "- "
        out = [f"{prefix}{tool_name} [{tool_id}]{meta_str}"]
        if desc:
            out.append(f"   Why: {desc}")
        if url:
            out.append(f"   Link: {url}")
        return out

    if group_by_category:
        grouped = {}
        for item in top:
            grouped.setdefault(item["category_label"], []).append(item)

        shown_total = 0
        for cat_label, items in grouped.items():
            if shown_total >= max_results:
                break
            lines.append(f"\n## {cat_label}")
            for item in items[:max_per_category]:
                if shown_total >= max_results:
                    break
                shown_total += 1
                lines.extend(_tool_summary_line(item))
    else:
        for i, item in enumerate(top, start=1):
            lines.extend([""] + _tool_summary_line(item, i))

    lines.append(
        "\n📋 Usage Reminder:\n"
        "- Verify authorization and applicable policy before use.\n"
        "- Prefer passive collection and official access paths.\n"
        "- Document sources, timestamps, and methodology."
    )

    return "\n".join(lines) + render_output_policy_block("AssignTools")

# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting anakrisis MCP server...")
    
    # Verify required files exist
    required_files = [
        RISK_RULES_FILE,
        DISALLOWED_ACTIONS_FILE,
        ASSIGNTOOLS_CATALOG_FILE,
        TEXT_ANALYZER_FILE,
        GRAPH_BUILDER_FILE,
        REPORT_REDACTION_FILE,
        OUTPUT_POLICY_FILE
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    if missing_files:
        logger.warning(f"Missing configuration files: {missing_files}")
        logger.warning("Server will use fallback rules")
    
    # Verify directories exist
    for directory in [PLAYBOOKS_DIR, REPORT_TEMPLATES_DIR]:
        if not directory.exists():
            logger.warning(f"Directory not found: {directory}")
            logger.warning("Creating directory...")
            directory.mkdir(parents=True, exist_ok=True)
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)