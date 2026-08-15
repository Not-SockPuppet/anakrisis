"""Word-boundary matching in the trigger engine and action-rule matcher."""
import anakrisis


def test_contains_any_requires_whole_word():
    trigger = {"type": "contains_any", "field": "goal", "values": ["contact"]}
    matched, _ = anakrisis._trigger_matches(trigger, {"goal": "collecting all contacts"})
    assert not matched, "'contact' must not fire inside 'contacts'"

    matched, evidence = anakrisis._trigger_matches(trigger, {"goal": "contact the vendor"})
    assert matched
    assert evidence == ["contact"]


def test_contains_any_matches_phrases():
    trigger = {"type": "contains_any", "field": "constraints", "values": ["pretend to be"]}
    matched, _ = anakrisis._trigger_matches(
        trigger, {"constraints": "create a profile and pretend to be a member"}
    )
    assert matched


def test_not_contains_any_uses_whole_words():
    # "signed" must not be satisfied by "assigned" — that would silently
    # suppress the missing-authorization factor.
    trigger = {
        "type": "not_contains_any",
        "field": "constraints",
        "values": ["signed"],
        "evaluate_if_field_non_empty": True,
    }
    matched, _ = anakrisis._trigger_matches(trigger, {"constraints": "assigned to me"})
    assert matched, "'assigned' does not contain the whole word 'signed'"

    matched, _ = anakrisis._trigger_matches(trigger, {"constraints": "signed engagement letter"})
    assert not matched


def test_action_rules_use_whole_words():
    rule = {"triggers": [{"type": "all_of", "values": ["send", "request"]}]}
    assert anakrisis._action_rule_matches(rule, "resend the password reset request") is None
    assert anakrisis._action_rule_matches(rule, "send a follow request") == "send + request"


def test_action_rule_contains_any_whole_word():
    rule = {"triggers": [{"type": "contains_any", "values": ["poke"]}]}
    assert anakrisis._action_rule_matches(rule, "spoke with a colleague") is None
    assert anakrisis._action_rule_matches(rule, "poke the account") == "poke"
