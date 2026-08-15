# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/Not-SockPuppet/anakrisis/security/advisories/new)
(Security → Report a vulnerability). Please do not open a public issue for a
security report.

Include the affected version or commit, reproduction steps, and the impact you
observed. Expect an initial response within 14 days.

## Scope

Anakrisis is a local MCP server. It makes no network calls, opens no listening
ports, and stores no credentials. The relevant security surface is therefore:

- **Filesystem access.** `CreateCase` writes under `~/anakrisis/cases/`. Case
  names are validated against a conservative pattern to prevent path traversal;
  report any input that escapes that directory.
- **Template and doctrine loading.** Report any tool input that causes a file
  outside the repository's `report_templates/` or `doctrine/` directories to be
  read.
- **Denial of service.** Report inputs that cause the server to hang or crash the
  host client.

## Not in scope

- The advisory nature of the tool. Anakrisis flags and warns; it does not enforce.
  A model or user choosing to ignore a hard stop is expected behavior, not a
  vulnerability. See [README](README.md) and [SECURITY posture](#security-model).
- The contents of the OSINT tool catalog (`doctrine/assigntools.yaml`), which
  lists publicly available tools.

## Security model

The guardrails in Anakrisis are advisory heuristics, not access controls. Risk
scoring, hard stops, and action review are keyword- and trigger-based, evaluated
against the text a user supplies. A euphemistic or deliberately obfuscated
description can pass a check that a plain description would fail — this is why a
`RulesOfEngagement` call that matches no rule is reported as unassessed rather
than cleared. Do not treat Anakrisis output as authorization, legal advice, or a
compliance control.
