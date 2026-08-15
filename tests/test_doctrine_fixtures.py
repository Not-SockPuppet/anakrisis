"""Run every test_cases fixture in doctrine/risk_rules.yaml against assess_risk.

These fixtures are the contract between the doctrine and the scoring engine:
docs/doctrine.md tells doctrine authors to keep them passing after any edit.
"""
import pytest
import yaml

import anakrisis


def _load_fixtures():
    with open(anakrisis.RISK_RULES_FILE, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    cases = rules.get("test_cases", [])
    assert cases, "risk_rules.yaml must ship a non-empty test_cases block"
    return cases


FIXTURES = _load_fixtures()


@pytest.mark.parametrize("case", FIXTURES, ids=[c["id"] for c in FIXTURES])
def test_risk_fixture(case):
    inp = case["input"]
    expected = case["expected"]

    tier, _summaries, triggered_ids, _substantive_ids = anakrisis.assess_risk(
        inp.get("goal", ""),
        inp.get("what_you_have", ""),
        inp.get("constraints", ""),
        actor_role=inp.get("actor_role", ""),
        method_class=inp.get("method_class", ""),
        jurisdiction_country=inp.get("jurisdiction_country", ""),
        jurisdiction_state=inp.get("jurisdiction_state", ""),
    )

    assert set(triggered_ids) == set(expected["triggered_factor_ids"]), (
        f"{case['id']}: triggered factors {sorted(triggered_ids)} "
        f"!= expected {sorted(expected['triggered_factor_ids'])}"
    )
    assert tier == expected["expected_tier_id"], (
        f"{case['id']}: tier {tier} != expected {expected['expected_tier_id']}"
    )

    # Recompute the score the same way the engine does (sum of factor scores,
    # clamped to the configured cap) and check it against the fixture.
    with open(anakrisis.RISK_RULES_FILE, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    scores = {f_["id"]: int(f_["score"]) for f_ in rules["risk_factors"]}
    cap = int(rules["evaluation_model"]["scoring"]["score_cap"])
    total = min(sum(scores[fid] for fid in triggered_ids), cap)
    assert total == expected["expected_score"], (
        f"{case['id']}: score {total} != expected {expected['expected_score']}"
    )
