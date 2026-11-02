"""The gate, the ledger, the chain, the replay engine and the compilers, without the instance."""

import copy
from datetime import datetime, timezone

from shopfloor import gate, ledger, policy
from shopfloor.cleanup import replay, required_approvers

FINANCE = {"id": "gl_actuals", "domain": "finance", "classification": "restricted", "owner": "o"}
CREDIT = {"id": "loan_book", "domain": "credit", "classification": "confidential", "owner": "o"}
RULES = [{"id": "ar-owner", "approver_kind": "dataset_owner"},
         {"id": "ar-sec", "approver_kind": "role", "approver_role": "security-analyst", "min_classification": "restricted"},
         {"id": "ar-ye", "approver_kind": "role", "approver_role": "finance-controller", "domain": "finance",
          "year_end_close_days": 10}]
POLICY = {"id": "pol-credit-analyst-credit-read", "role": "credit-analyst", "domain": "credit",
          "max_classification": "confidential", "privilege": "read", "effect": "allow", "requires_approval": False,
          "description": "x"}


def at(y, m, d):
    return datetime(y, m, d, 12, tzinfo=timezone.utc)


def test_approval_rules_decide_who_approves():
    assert required_approvers(RULES, CREDIT, at(2025, 6, 1)) == {"owner"}
    assert required_approvers(RULES, FINANCE, at(2025, 6, 1)) == {"owner", "security-analyst"}
    assert required_approvers(RULES, FINANCE, at(2026, 3, 25)) == {"owner", "security-analyst", "finance-controller"}


def test_replay_catches_a_retired_rule_that_still_acts():
    hist = [{"request": "r1", "dataset": FINANCE, "opened": at(2026, 3, 25), "rejected": False,
             "approvers": {"owner", "security-analyst", "finance-controller"}},
            {"request": "r2", "dataset": CREDIT, "opened": at(2026, 6, 1), "rejected": False, "approvers": {"owner"}}]
    assert replay(hist, RULES) == []
    diffs = replay(hist, RULES[:2])
    assert [d["request"] for d in diffs] == ["r1"]


def _decide(step="st-approve", **kw):
    req = {"id": "RITM1", "requested_at": "2026-10-30T09:00:00Z", "privilege": "read"}
    args = dict(role="credit-analyst", policies=[POLICY], approval_rules=RULES, capability=None, stops=[],
                approvals=set())
    args.update(kw)
    return gate.decide(step, req, kw.pop("dataset", CREDIT), {"id": "a", "registered": True}, **args)


def test_gate_declared_policy_needs_no_approval_but_outside_policy_does():
    assert _decide()["rule"] == "declared_policy"
    assert _decide(role="quantitative-researcher")["effect"] == "checkpoint"


def test_gate_fails_closed_on_stop_unregistered_and_error():
    stop = {"request": "RITM1", "rule": "device_posture", "decided_by": "soc", "reason": "Host not compliant"}
    assert _decide(stops=[stop])["effect"] == "deny"
    assert gate.decide("st-approve", {"id": "RITM1"}, CREDIT, {"id": "x", "registered": False}, role=None,
                       policies=[], approval_rules=[], capability=None, stops=[], approvals=set())["effect"] == "deny"
    broken = gate.decide("st-approve", {"id": "RITM1"}, CREDIT, {"id": "a", "registered": True}, role="r",
                         policies=None, approval_rules=None, capability=None, stops=[], approvals=set())
    assert broken["effect"] == "deny" and broken["rule"] == "gate_error"


def test_gate_respects_the_autonomy_ladder():
    cap = {"autonomy_level": "act_with_checkpoint"}
    assert _decide("st-provision", capability=cap)["effect"] == "checkpoint"
    assert _decide("st-provision", capability={"autonomy_level": "act"})["effect"] == "allow"
    assert _decide("st-provision", capability=None)["effect"] == "deny"


def test_ledger_proposes_on_evidence_and_demotes_at_once():
    cap = ledger.Capability("c1", "agent", "st-approve", "act_with_checkpoint")
    for i in range(40):
        ledger.observe(cap, f"t{i}", True)
    assert ledger.propose(cap) is None, "40 of 40 is not yet enough evidence"
    for i in range(40, 120):
        ledger.observe(cap, f"t{i}", True)
    up = ledger.propose(cap)
    assert up and up["to_level"] == "act" and up["evidence"]
    down = ledger.demote(cap, "later", breach="t120 reversed")
    assert down["to_level"] == "assist" and cap.evidence == []


def test_chain_verifies_and_detects_tampering():
    events = ledger.chain([{"id": f"e{i}", "kind": "completed", "request": "RITM1"} for i in range(5)])
    assert ledger.verify(events) == []
    tampered = copy.deepcopy(events)
    tampered[2]["kind"] = "approved"
    assert ledger.verify(tampered) == ["e2"]


def test_immuta_payloads_validate_and_a_broken_one_does_not():
    payloads = policy.compile_immuta([POLICY])
    assert len(payloads) == 3 and policy.check_immuta(payloads) == []
    bad = copy.deepcopy(payloads[0])
    del bad["actions"]["entitlements"]
    assert policy.check_immuta([bad])


def test_policies_are_vocabulary_instances():
    assert policy.validate_policies([POLICY], [{"id": "credit-analyst", "name": "Credit analyst"}]) == []
    bad = dict(POLICY, max_classification="secret")
    assert policy.validate_policies([bad], [])


def test_declared_policy_does_not_override_a_rule_that_only_acts_in_a_window():
    """The year-end rule is held because it still decides who approves in the close. A declared policy must not
    silently skip it there."""
    controller = {"id": "pol-fc", "role": "finance-controller", "domain": "finance",
                  "max_classification": "restricted", "privilege": "read", "effect": "allow",
                  "requires_approval": False, "description": "x"}
    args = dict(role="finance-controller", policies=[controller], approval_rules=RULES, capability=None, stops=[],
                approvals=set())
    june = {"id": "R1", "requested_at": "2026-06-01T09:00:00Z", "privilege": "read"}
    close = {"id": "R2", "requested_at": "2026-03-25T09:00:00Z", "privilege": "read"}
    actor = {"id": "a", "registered": True}
    assert gate.decide("st-approve", june, FINANCE, actor, **args)["rule"] == "declared_policy"
    assert gate.decide("st-approve", close, FINANCE, actor, **args)["effect"] == "checkpoint"


def test_an_anchored_chain_catches_an_edit_even_when_the_chain_is_rebuilt():
    events = ledger.chain([{"id": f"e{i}", "kind": "completed", "request": "RITM1"} for i in range(5)])
    anchor = ledger.head(events)
    assert ledger.verify(events, anchor) == []
    forged = copy.deepcopy(events)
    forged[2]["kind"] = "approved"
    ledger.chain(forged)  # whoever edits can rebuild the hashes
    assert ledger.verify(forged) == [], "an unanchored chain cannot tell"
    assert ledger.verify(forged, anchor), "the anchor held elsewhere can"


def test_autonomy_starts_at_assist_and_rises_only_on_a_persons_confirmation():
    cap = ledger.Capability("c1", "agent", "st-provision")
    assert cap.autonomy_level == "assist"
    for i in range(200):
        ledger.observe(cap, f"t{i}", True)
    proposal = ledger.propose(cap)
    assert proposal and proposal["to_level"] == "act_with_checkpoint"
    assert ledger.apply_confirmed(cap, [], "now") is None and cap.autonomy_level == "assist"
    yes = [{"id": proposal["id"], "change_kind": "autonomy", "verdict": "approve", "decided_by": "p",
            "decided_at": "2026-11-01T09:00:00Z"}]
    change = ledger.apply_confirmed(cap, yes, "now")
    assert change and cap.autonomy_level == "act_with_checkpoint" and change["confirmation"] == proposal["id"]


def test_each_rung_is_earned_by_evidence_at_the_rung_below():
    cap = ledger.Capability("c1", "agent", "st-provision")
    for i in range(200):
        ledger.observe(cap, f"t{i}", True)

    def yes(p):
        return [{"id": p["id"], "change_kind": "autonomy", "verdict": "approve", "decided_by": "p",
                 "decided_at": "2026-11-01T09:00:00Z"}]
    first = ledger.propose(cap)
    assert ledger.apply_confirmed(cap, yes(first), "now")
    assert ledger.propose(cap) is None, "the evidence that earned this rung cannot earn the next one"
