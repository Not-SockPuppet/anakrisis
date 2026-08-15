# Contributing

Thanks for your interest in Anakrisis. This document covers how to set up a
development environment, run the checks, and submit changes.

## Development setup

Requires Python 3.10 or newer.

```bash
git clone https://github.com/Not-SockPuppet/anakrisis.git
cd anakrisis
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the server, the test tooling (pytest), and the linter (ruff).

## Running the checks

```bash
ruff check .
pytest -q
```

Both run in CI on Python 3.10–3.13 for every pull request. Please run them
locally before opening a PR.

## Editing doctrine

Most behavior lives in the YAML files under `doctrine/`, `playbooks/`, and
`report_templates/`, not in Python. See [docs/doctrine.md](docs/doctrine.md) for
how each file is evaluated.

`doctrine/risk_rules.yaml` ships a `test_cases:` block that pins expected factors,
scores, and tiers for ten scenarios. `tests/test_doctrine_fixtures.py` runs every
one against the scoring engine. If you change a risk factor, a trigger, or a tier
range, update the affected fixtures in the same commit so the suite stays green.

## Trigger matching

`contains_any` and `not_contains_any` triggers match whole words and phrases, not
substrings — `contact` does not fire on `contacts`. When both an inflected form and
its base should trigger (`scrape` and `scraping`), list both explicitly.

## Pull requests

- Keep changes focused; one logical change per PR.
- Update `CHANGELOG.md` under the `Unreleased` heading.
- Update the relevant docs (`README.md`, `docs/`) when behavior or interfaces change.
- Describe what changed and why in the PR description.

## Reporting security issues

Do not open a public issue for a vulnerability. Follow [SECURITY.md](SECURITY.md).
