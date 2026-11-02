"""The record read from the sources must say what happened. Without the instance: the world's ServiceNow rows
stand in for the Table API, and the fixtures are the same files the demo reads."""

from collections import Counter

from shopfloor import ingest, live
from shopfloor.seed import fixtures
from shopfloor.seed.world import NOW, build


def offline_estate(w) -> ingest.Estate:
    """The estate as Estate.__init__ would read it from the seeded instance, from the world instead."""
    e = ingest.Estate.__new__(ingest.Estate)
    e.sn, e.now = None, NOW
    e.generated_item = None
    e.items = [{"sys_id": it["sys_id"], "name": it["name"], "short_description": it["name"], "active": "true"}
               for it in w.items]
    e.ritms = [{**r, "state": str(r.get("state", "")), "closed_at": r.get("closed_at")} for r in w.requests]
    e.approvals = [{**a, "source_table": "sc_req_item"} for a in w.approvals]
    e.tasks = list(w.tasks)
    e.users = {u["sys_id"]: u for u in w.users}
    e.rules, e.fields = [], []
    e.veza = fixtures.veza(w)
    e.activity = fixtures.activity(w)
    e.armis = w.armis_assets
    e.moveworks = w.moveworks_intake
    e.spans = fixtures.spans(w)
    e.datasets = w.datasets
    return e


def planted_outcomes(w) -> dict[str, str]:
    """What the generator says happened to each fulfilled request: the planted truth."""
    return {r["number"]: r["outcome"] for r in w.requests if r.get("outcome") and r["outcome"] != "rejected"}


def test_provisioning_outcomes_are_read_as_planted():
    """A reversal is a fact in the authority system's history. Reading the current grant alone loses every
    reversal that a later request re-granted, and the agent's record looks better than it is."""
    w = build()
    rec = ingest.record(offline_estate(w))
    truth = planted_outcomes(w)
    got = {t["request"]: t["outcome"]["status"] for t in rec["tasks"] if t["step"] == ingest.PROVISION}
    assert set(got) == set(truth)
    wrong = {k: (truth[k], got[k]) for k in truth if truth[k] != got[k]}
    assert wrong == {}, f"{len(wrong)} of {len(truth)} outcomes differ: {dict(list(wrong.items())[:5])}"


def test_the_agents_evidence_is_its_planted_record():
    w = build()
    rec = ingest.record(offline_estate(w))
    cap = live.provisioning_capability(rec)
    agent_tasks = {t["request_item"] for t in w.tasks if t["by_agent"]}
    planted = Counter(r["outcome"] for r in w.requests if r["sys_id"] in agent_tasks)
    assert len(cap.evidence) == sum(planted.values())
    assert cap.accepted == planted["accepted"]
