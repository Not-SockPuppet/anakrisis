# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-15

First tagged release. Nine-tool MCP server for OSINT investigation planning:
deterministic risk scoring against local YAML doctrine, hard-stop rules, case
scaffolding, and doctrine-bound analysis and redaction prompts. Advisory only —
it classifies, scores, and warns; it does not collect data or block execution.

### Added
- Container images published to `ghcr.io/not-sockpuppet/anakrisis` for
  `linux/amd64` and `linux/arm64`, built and pushed automatically on a version
  tag with a signed provenance attestation.
- `pyproject.toml` with project metadata, `requires-python = ">=3.10"`, an
  `anakrisis-server` console entry point, and ruff/pytest configuration.
- Test suite: the `risk_rules.yaml` fixtures now run against the scoring engine,
  plus coverage for whole-word trigger matching, report-template path handling,
  and untrusted-content fencing.
- CI running ruff and pytest on Python 3.10–3.14, plus a job that builds the
  container image, drives it over stdio, and requires a valid MCP `initialize`
  result and a non-root runtime user.
- Dependabot for GitHub Actions, Python dependencies, and the Docker base image.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`,
  `.dockerignore`, and issue/PR templates.

### Changed
- Trigger matching (`contains_any`, `not_contains_any`, and the action-rule
  matcher) now matches whole words and phrases instead of substrings, so a value
  like `contact` no longer fires inside `contacts`. Inflected forms the old
  behaviour covered implicitly (`scraping`, `bypassing`, …) are listed explicitly
  in the affected doctrine triggers.
- The `mcp` dependency is capped below 2.0. mcp 2.x relocated
  `mcp.server.fastmcp`, which the server imports; an unpinned install would fail
  to start.
- Container base image moved to `python:3.14-slim`.
- User-facing text across the README, docs, launcher, and tool output reworded to
  be plainer and less promotional.

### Fixed
- Untrusted investigator-supplied text is fenced between explicit markers in the
  `TextAnalyzer`, `GraphBuilder`, and `ReportRedaction` prompts, with attempts to
  forge those markers neutralized and an instruction to treat the region as data.
  Previously such text — routinely authored by the subject of an investigation —
  was interpolated with no delimiter and could impersonate the surrounding prompt.
- `ReportTemplate` no longer follows path-traversal components in
  `investigation_type` / `audience`; unsafe values fall through to the default
  template.
- Case names matching a Windows reserved device name (`CON`, `PRN`, `NUL`,
  `COM1`–`COM9`, `LPT1`–`LPT9`) are rejected rather than producing a directory
  that cannot be created on Windows.
- Corrected the stale `risk_rules.yaml` test fixtures (TC06, TC07, TC09), which
  disagreed with the scoring engine's actual output.
- The README walkthrough uses inputs that reproduce the output it shows.

[Unreleased]: https://github.com/Not-SockPuppet/anakrisis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Not-SockPuppet/anakrisis/releases/tag/v0.1.0
