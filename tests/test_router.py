"""Router classification: mechanical steps are easy, judgment is hard,
and anything unknown defaults to hard (spend money before losing accuracy)."""

from agentledger import classify_step, route


def test_easy_kinds():
    for kind in ("extract", "classify", "format"):
        assert classify_step(kind) == "easy"
        assert route(kind) == "cheap"


def test_hard_kinds():
    for kind in ("reason", "plan", "synthesize", "judge"):
        assert classify_step(kind) == "hard"
        assert route(kind) == "frontier"


def test_unknown_kind_defaults_to_hard():
    assert classify_step("teleport") == "hard"
    assert route("teleport") == "frontier"


def test_classification_is_case_and_space_insensitive():
    assert classify_step("  Extract ") == "easy"
    assert route("REASON") == "frontier"
