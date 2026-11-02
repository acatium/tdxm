"""Clean-up decisions: a change is applied only if history proves it and a person confirms it. Without the
instance: the plan, the history and the agent's translation are plain data."""

import copy
from datetime import datetime, timezone

from shopfloor.cleanup import decide

FINANCE = {"id": "gl_actuals", "domain": "finance", "classification": "restricted", "owner": "o"}
CREDIT = {"id": "loan_book", "domain": "credit", "classification": "confidential", "owner": "o"}


def at(y, m, d):
    return datetime(y, m, d, 12, tzinfo=timezone.utc)


HIST = [{"request": "r1", "dataset": FINANCE, "opened": at(2026, 3, 25), "rejected": False,
         "approvers": {"owner", "security-analyst", "finance-controller"}},
        {"request": "r2", "dataset": FINANCE, "opened": at(2026, 6, 1), "rejected": False,
         "approvers": {"owner", "security-analyst"}},
        {"request": "r3", "dataset": CREDIT, "opened": at(2026, 6, 2), "rejected": False, "approvers": {"owner"}}]
DECLARATIONS = {
    "approval_rules": [
        {"id": "own", "approver_kind": "dataset_owner"},
        {"id": "sec", "approver_kind": "role", "approver_role": "security-analyst", "min_classification": "restricted"},
        {"id": "ye", "approver_kind": "role", "approver_role": "finance-controller", "domain": "finance",
         "year_end_close_days": 10}],
    "source_rules": [{"rule": "r-own", "approval_rule": "own", "note": ""},
                     {"rule": "r-sec", "approval_rule": "sec", "note": ""},
                     {"rule": "r-ye", "approval_rule": "ye", "note": ""}]}


def steps():
    def br(i, plan, usage):
        return {"id": i, "kind": "business_rule", "name": i, "plan": plan, "usage_180d": usage}
    return [br("r-own", "declare", 50), br("r-sec", "declare", 20), br("r-ye", "retire", 0),
            br("r-legacy", "retire", 0), br("r-unknown", "revert_to_base", -1),
            {"id": "i-old", "kind": "catalogue_item", "name": "old item", "plan": "retire", "usage_180d": 0}]


def status(result):
    return {s["id"]: s["status"] for s in result["plan"]}


def test_a_faithful_translation_holds_the_rule_that_still_acts():
    r = decide(steps(), HIST, DECLARATIONS)
    assert r["full_model_diffs"] == 0
    assert status(r)["r-ye"] == "held"


def test_a_translation_that_misses_a_rule_holds_everything():
    """The defence must not depend on the agent being right: if the declared model does not reproduce
    history, nothing is proposed."""
    wrong = copy.deepcopy(DECLARATIONS)
    wrong["source_rules"][2]["approval_rule"] = None  # the agent did not see the year-end rule as approval logic
    r = decide(steps(), HIST, wrong)
    assert r["full_model_diffs"] > 0
    assert set(status(r).values()) <= {"held", "kept"}, status(r)


def test_a_translation_with_the_wrong_window_holds_everything():
    wrong = copy.deepcopy(DECLARATIONS)
    wrong["approval_rules"][2]["year_end_close_days"] = 3
    r = decide(steps(), HIST, wrong)
    assert set(status(r).values()) <= {"held", "kept"}, status(r)


def test_unknown_usage_with_nothing_to_replay_is_held():
    assert status(decide(steps(), HIST, DECLARATIONS))["r-unknown"] == "held"


def _confirmed(result, verdict="approve"):
    from shopfloor.cleanup import plan_proposal
    return [{"id": plan_proposal(result)["id"], "change_kind": "repair", "verdict": verdict, "decided_by": "a.person",
             "decided_at": "2026-11-01T09:00:00Z"}]


def _with_declarations(decided: dict) -> dict:
    return {**decided, "declarations": DECLARATIONS, "datasets": [FINANCE, CREDIT],
            "roles": [{"id": "security-analyst", "name": "Security analyst"},
                      {"id": "finance-controller", "name": "Finance controller"}]}


def test_nothing_is_approved_without_a_persons_confirmation():
    from shopfloor.cleanup import confirm_plan
    r = confirm_plan(_with_declarations(decide(steps(), HIST, DECLARATIONS)), [])
    assert "approved" not in status(r).values()
    assert status(r)["r-own"] == "proposed" and r["proposal"]["verdict"] is None


def test_a_confirmation_approves_exactly_what_was_proposed():
    from shopfloor.cleanup import confirm_plan
    base = _with_declarations(decide(steps(), HIST, DECLARATIONS))
    ok = _confirmed(copy.deepcopy(base))
    r = confirm_plan(copy.deepcopy(base), ok)
    assert status(r)["r-own"] == "approved" and status(r)["r-ye"] == "held"
    changed = steps()
    changed[0]["plan"] = "revert_to_base"  # the proposal changed after the person decided
    r2 = confirm_plan(_with_declarations(decide(changed, HIST, DECLARATIONS)), ok)
    assert "approved" not in status(r2).values()


def test_a_rejection_applies_nothing():
    from shopfloor.cleanup import confirm_plan
    base = _with_declarations(decide(steps(), HIST, DECLARATIONS))
    r = confirm_plan(copy.deepcopy(base), _confirmed(copy.deepcopy(base), "reject"))
    assert "approved" not in status(r).values() and status(r)["r-own"] == "rejected"


def test_compiled_rules_replace_retired_scripts_but_never_a_held_one():
    from shopfloor.cleanup import compiled_rules
    r = {**decide(steps(), HIST, DECLARATIONS), "declarations": DECLARATIONS}
    assert [x["id"] for x in compiled_rules(r)] == ["own", "sec"]


def test_a_rejection_wins_over_an_approval_of_the_same_proposal():
    from shopfloor import confirm
    c = [{"id": "p1", "verdict": "approve", "decided_by": "a"}, {"id": "p1", "verdict": "reject", "decided_by": "b"}]
    assert confirm.verdict(c, "p1") == "reject"
    assert confirm.verdict(list(reversed(c)), "p1") == "reject"


def test_an_untestable_rule_is_held_unless_usage_shows_it_dead():
    """A rule the replay cannot test is switched off only when the record shows it never acts. Anything else
    (replace, revert, or a retire that usage contradicts) waits for its replacement or a person."""
    s = steps()
    s[4] = {"id": "r-glue", "kind": "business_rule", "name": "r-glue", "plan": "replace_with_adapter", "usage_180d": 500}
    s.append({"id": "r-busy", "kind": "business_rule", "name": "r-busy", "plan": "retire", "usage_180d": 12})
    st = status(decide(s, HIST, DECLARATIONS))
    assert st["r-glue"] == "held" and st["r-busy"] == "held"
    assert st["r-legacy"] == "proposed", "retire at zero usage is proposed"


DATASETS = [FINANCE, CREDIT]
ROLES = [{"id": "security-analyst", "name": "Security analyst"}, {"id": "finance-controller", "name": "Finance controller"}]


def _result(datasets=DATASETS, roles=ROLES):
    return {**_with_declarations(decide(steps(), HIST, DECLARATIONS)), "datasets": datasets, "roles": roles}


def test_the_confirmation_covers_what_is_installed_on_the_platform():
    """The person confirms the business rules and the catalogue item that will land on the platform, not just the
    plan. A change to who owns a dataset changes the compiled script, so it changes the proposal."""
    from shopfloor.cleanup import plan_proposal, platform_payload
    base = plan_proposal(_result())
    other_owner = [dict(FINANCE, owner="someone.else"), CREDIT]
    assert plan_proposal(_result(datasets=other_owner))["id"] != base["id"]
    other_role = [ROLES[0], {"id": "finance-controller", "name": "Controller"}]
    assert plan_proposal(_result(roles=other_role))["id"] != base["id"]
    payload = platform_payload(_result())
    assert {c["f"]["name"] for c in payload["compiled"]} == {"Approval rules (compiled from the model)",
                                                             "Request fields (compiled from the model)"}
    assert payload["item"]["f"]["name"] == "Request access to data"


def test_a_rule_the_compiled_request_fields_replace_is_proposed_even_though_the_replay_cannot_test_it():
    """The cost-centre script requires a field and a pattern. The replay sees no approval logic in it, but the
    compiled request-fields rule enforces that slot from the model, so it is replaced, not merely retired.
    A declare whose target is not a slot the compiler enforces stays held."""
    s = steps()
    s[4] = {"id": "r-cc", "kind": "business_rule", "name": "Require cost centre", "plan": "declare", "usage_180d": 651,
            "target_term": "org:ContosoAccessRequest.cost_centre"}
    s.append({"id": "r-ev", "kind": "business_rule", "name": "Close on last task", "plan": "declare", "usage_180d": 20,
              "target_term": "work:WorkEvent"})
    st = status(decide(s, HIST, DECLARATIONS, replaced={"dataset", "privilege", "cost_centre", "justification"}))
    assert st["r-cc"] == "proposed" and st["r-ev"] == "held"
    assert status(decide(steps()[:4] + [s[4]], HIST, DECLARATIONS))["r-cc"] == "held", "nothing replaces it without the compiler"
