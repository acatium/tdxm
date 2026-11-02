"""Declared policy from approval history: the evidence, the cap and the out-of-sample measure. Plain data."""

from shopfloor import policy


def cell(n, ok):
    return {"n": n, "approved": ok, "requests": []}


TABLE = {
    ("Credit analyst", "credit", "confidential", "read"): cell(400, 399),
    # The owner approved nearly all of these, but security refused some: the whole chain is the evidence.
    ("Credit analyst", "credit", "restricted", "read"): cell(230, 212),
    ("Quantitative researcher", "markets", "public", "read"): cell(170, 170),
    ("Quantitative researcher", "markets", "internal", "read"): cell(30, 25),  # some review happens here
    ("Quantitative researcher", "markets", "confidential", "read"): cell(200, 200),
    ("Finance controller", "finance", "restricted", "read"): cell(300, 300),
}


def by_id(ps):
    return {p["id"]: p["max_classification"] for p in ps}


def test_a_policy_never_reaches_past_a_classification_that_failed_the_bar():
    got = by_id(policy.derive(TABLE))
    assert got["pol-credit-analyst-credit-read"] == "confidential"
    assert got["pol-quantitative-researcher-markets-read"] == "public", "internal failed, so confidential is not reached"


def test_above_confidential_only_the_data_owner_can_confirm():
    datasets = [{"id": "gl", "domain": "finance", "owner": "fin.owner"}]
    props = {p["policy"]["id"]: p for p in policy.proposals(policy.derive(TABLE), datasets, TABLE)}
    fc = props["pol-finance-controller-finance-read"]
    assert fc["needs"] and fc["owners"] == ["fin.owner"]
    def conf(who):
        return [{"id": fc["id"], "change_kind": "declared_policy", "verdict": "approve", "decided_by": who,
                 "decided_at": "2026-11-01T09:00:00Z"}]
    assert policy.confirmed([fc], conf("someone.else"))[0] == []
    assert policy.confirmed([fc], conf("fin.owner"))[0] == [fc["policy"]]


def test_rejected_requests_are_not_counted_as_avoidable():
    rec = {"datasets": [{"id": "lb", "domain": "credit", "classification": "confidential"}],
           "requests": [{"id": f"R{i}", "dataset": "lb", "privilege": "read", "on_behalf_of": "ann",
                         "requested_at": "2026-01-01T00:00:00Z"} for i in range(4)],
           "tasks": [{"request": "R3", "step": "st-approve", "outcome": {"status": "failed"}}]}
    pol = policy.derive(TABLE)
    got = policy.avoidable(rec, pol, {"ann": "Credit analyst"})
    assert got == {"requests_approved": 3, "covered": 3, "share": 1.0, "covered_but_rejected": 1}


def test_a_policy_stops_at_a_classification_with_no_evidence():
    gap = {("Data engineer", "markets", "public", "read"): cell(200, 200),
           ("Data engineer", "markets", "restricted", "read"): cell(200, 200)}
    assert by_id(policy.derive(gap))["pol-data-engineer-markets-read"] == "public"


def test_no_policy_over_a_domain_a_windowed_rule_touches():
    """Immuta and Veza grants have no window, so a policy there would skip the year-end rule all year."""
    windowed = [{"id": "ye", "approver_kind": "role", "approver_role": "finance-controller", "domain": "finance",
                 "year_end_close_days": 10}]
    assert "pol-finance-controller-finance-read" not in by_id(policy.derive(TABLE, windowed))
    assert "pol-credit-analyst-credit-read" in by_id(policy.derive(TABLE, windowed))


def test_above_confidential_a_rejection_from_anyone_counts():
    datasets = [{"id": "gl", "domain": "finance", "owner": "fin.owner"}]
    fc = {p["policy"]["id"]: p for p in policy.proposals(policy.derive(TABLE), datasets, TABLE)}[
        "pol-finance-controller-finance-read"]
    c = [{"id": fc["id"], "change_kind": "declared_policy", "verdict": "approve", "decided_by": "fin.owner",
          "decided_at": "2026-11-01T09:00:00Z"},
         {"id": fc["id"], "change_kind": "declared_policy", "verdict": "reject", "decided_by": "someone.else",
          "decided_at": "2026-11-01T09:00:00Z"}]
    assert policy.confirmed([fc], c)[0] == []


def test_the_minimum_cell_is_the_smallest_that_can_clear_the_bar():
    from shopfloor.diagnose import POLICY_BOUND, POLICY_MIN, wilson_lower
    assert wilson_lower(POLICY_MIN, POLICY_MIN) >= POLICY_BOUND
    assert wilson_lower(POLICY_MIN - 1, POLICY_MIN - 1) < POLICY_BOUND


def test_no_policy_is_derived_from_a_translation_the_replay_rejected():
    """If the declared model does not reproduce history, nothing is proposed: not a repair, and not a policy
    derived under that model's rules either."""
    import pytest
    ok = {"full_model_diffs": 0, "declarations": {"approval_rules": [{"id": "own", "approver_kind": "dataset_owner"}]}}
    assert policy.rules_proved(ok) == ok["declarations"]["approval_rules"]
    with pytest.raises(ValueError, match="does not reproduce history"):
        policy.rules_proved({**ok, "full_model_diffs": 3})


def _record(year_one: int, year_two: int):
    """One cell, with requests the owner approved, split across the demo's two years."""
    reqs, tasks = [], []
    for i in range(year_one + year_two):
        at = "2025-03-01T00:00:00Z" if i < year_one else "2026-03-01T00:00:00Z"
        reqs.append({"id": f"R{i}", "dataset": "lb", "privilege": "read", "on_behalf_of": "ann", "requested_at": at})
        tasks.append({"id": f"A{i}", "request": f"R{i}", "step": "st-approve", "actor": "own", "started_at": at,
                      "outcome": {"status": "accepted"}})
    return {"datasets": [{"id": "lb", "name": "Loan book", "platform": "p", "domain": "credit",
                          "classification": "confidential", "owner": "own"}],
            "actors": [{"id": "ann", "title": "Credit analyst"}, {"id": "own", "title": "Data owner"}],
            "requests": reqs, "tasks": tasks}


def test_policy_is_derived_from_year_one_and_measured_on_year_two(tmp_path, monkeypatch):
    """Remove the split from either side and this fails: a cell with evidence only in year two must not
    become policy, and the measurement must count year two alone."""
    import json
    from shopfloor import run
    monkeypatch.setattr(run, "VAR", tmp_path)
    cleanup = {"full_model_diffs": 0, "declarations": {"approval_rules": [{"id": "own", "approver_kind": "dataset_owner"}]}}
    (tmp_path / "cleanup.json").write_text(json.dumps(cleanup))
    (tmp_path / "record.json").write_text(json.dumps(_record(year_one=0, year_two=200)))
    assert run.policy_step()["derived"] == [], "evidence only in year two derives nothing"
    (tmp_path / "record.json").write_text(json.dumps(_record(year_one=200, year_two=40)))
    out = run.policy_step()
    assert [p["id"] for p in out["derived"]] == ["pol-credit-analyst-credit-read"]
    assert out["measured"]["avoidable"]["requests_approved"] == 40, "measured on year two alone"


def test_a_rejected_translation_derives_no_policy_in_the_run(tmp_path, monkeypatch):
    import json
    from shopfloor import run
    monkeypatch.setattr(run, "VAR", tmp_path)
    (tmp_path / "cleanup.json").write_text(json.dumps({"full_model_diffs": 2, "declarations": {"approval_rules": []}}))
    (tmp_path / "record.json").write_text(json.dumps(_record(year_one=200, year_two=40)))
    out = run.policy_step()
    assert out["derived"] == [] and out["proposals"] == [] and "does not reproduce history" in out["refused"]


def test_the_policy_proposal_names_the_rejections_it_would_override():
    datasets = [{"id": "lb", "domain": "credit", "owner": "cr.owner"}]
    measured = {"requests_approved": 400, "covered": 120, "share": 0.3, "covered_but_rejected": 3}
    [p] = [x for x in policy.proposals(policy.derive(TABLE), datasets, TABLE, measured) if x["policy"]["domain"] == "credit"]
    assert "3 that a person rejected" in p["summary"]
    assert p["evidence"]["measured_out_of_sample"] == measured
    assert p["id"] == next(x["id"] for x in policy.proposals(policy.derive(TABLE), datasets, TABLE)
                           if x["policy"]["domain"] == "credit"), "the measurement is evidence, not content"
