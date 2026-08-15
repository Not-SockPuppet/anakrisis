# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `pyproject.toml` with project metadata, `requires-python = ">=3.10"`, an
  `anakrisis-server` console entry point, and ruff/pytest configuration.
- Test suite under `tests/`: the `risk_rules.yaml` fixtures now run against the
  scoring engine, plus coverage for whole-word trigger matching and report-template
  path handling.
- GitHub Actions CI running ruff and pytest on Python 3.10–3.13.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates.

### Changed
- Trigger matching (`contains_any`, `not_contains_any`, and the action-rule
  matcher) now matches whole words and phrases instead of substrings, so a value
  like `contact` no longer fires inside `contacts`. Inflected forms that the old
  substring behavior covered implicitly (e.g. `scraping`, `bypassing`) are now
  listed explicitly in the affected doctrine triggers.
- Capped the `mcp` dependency below 2.0. mcp 2.x relocated `mcp.server.fastmcp`,
  which the server imports; an unpinned install would otherwise fail to start.
- Reworded tool output and documentation to be plainer and less promotional.

### Fixed
- `ReportTemplate` no longer follows path-traversal components in
  `investigation_type` / `audience`; unsafe values fall through to the default
  template.
- Corrected the stale `risk_rules.yaml` test fixtures (TC06, TC07, TC09) to match
  the scoring engine's actual output.
- The README walkthrough now uses inputs that reproduce the output it shows.

## [0.1.0] - 2026-08-15

Initial public version: nine-tool MCP server for OSINT investigation planning,
deterministic risk scoring against local YAML doctrine, hard-stop rules, case
scaffolding, and doctrine-bound analysis/redaction prompts.

[Unreleased]: https://github.com/Not-SockPuppet/anakrisis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Not-SockPuppet/anakrisis/releases/tag/v0.1.0
