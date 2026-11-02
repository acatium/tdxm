"""The business rules compiled from the model, run as the platform will run them. Node stands in for the Rhino
engine and a few lines of Glide stand-in for the Table API; the decisions must match the Python replay engine on
the same cases. A missing node fails the test: it is the gate."""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from shopfloor.cleanup import compile_platform, required_approvers, slug

HARNESS = Path(__file__).parent / "harness" / "glide.js"
RULES = [{"id": "own", "approver_kind": "dataset_owner"},
         {"id": "sec", "approver_kind": "role", "approver_role": "security-analyst", "min_classification": "restricted"},
         {"id": "ye", "approver_kind": "role", "approver_role": "finance-controller", "domain": "finance",
          "year_end_close_days": 10}]
DATASETS = [{"id": "gl_actuals", "domain": "finance", "classification": "restricted", "owner": "fin.owner"},
            {"id": "loan_book", "domain": "credit", "classification": "confidential", "owner": "cr.owner"},
            {"id": "budget", "domain": "finance", "classification": "internal", "owner": "fin.owner"}]
ROLES = [{"id": "security-analyst", "name": "Security analyst"}, {"id": "finance-controller", "name": "Finance controller"}]
USERS = [{"sys_id": "u-fin", "user_name": "fin.owner", "title": "Data owner"},
         {"sys_id": "u-cr", "user_name": "cr.owner", "title": "Data owner"},
         {"sys_id": "u-sec", "user_name": "sec.one", "title": "Security analyst"},
         {"sys_id": "u-fc", "user_name": "fc.one", "title": "Finance controller"}]
CASES = [("gl_actuals", "2026-03-25 09:00:00"), ("gl_actuals", "2026-03-21 09:00:00"), ("gl_actuals", "2026-03-22 00:00:00"),
         ("gl_actuals", "2026-06-01 09:00:00"), ("loan_book", "2026-03-25 09:00:00"), ("budget", "2026-03-31 23:00:00"),
         ("budget", "2026-04-01 00:00:00")]


def _run(script: str, cases: list[dict]) -> list[dict]:
    node = shutil.which("node")
    assert node, "node is needed to run the compiled rules locally"
    p = subprocess.run([node, str(HARNESS)], input=json.dumps({"script": script, "users": USERS, "cases": cases}),
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def _who(sys_ids: list[str], dataset: dict) -> set[str]:
    by_id = {u["sys_id"]: u for u in USERS}
    return {"owner" if by_id[s]["user_name"] == dataset["owner"] else slug(by_id[s]["title"]) for s in sys_ids}


def test_the_compiled_approval_rule_decides_as_the_replay_engine_does():
    compiled = compile_platform(RULES, DATASETS, ROLES)
    script = next(c["f"]["script"] for c in compiled if c["f"]["name"].startswith("Approval rules"))
    got = _run(script, [{"fields": {"u_dataset": d, "opened_at": at}} for d, at in CASES])
    datasets = {d["id"]: d for d in DATASETS}
    for (d, at), r in zip(CASES, got):
        opened = datetime.strptime(at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        assert _who(r["approvers"], datasets[d]) == required_approvers(RULES, datasets[d], opened), (d, at)


def test_the_compiled_rule_is_seen_to_disagree_when_the_window_differs():
    compiled = compile_platform(RULES, DATASETS, ROLES)
    script = next(c["f"]["script"] for c in compiled if c["f"]["name"].startswith("Approval rules"))
    r = _run(script.replace('"year_end_from_day": 22', '"year_end_from_day": 26'), [{"fields": {"u_dataset": "gl_actuals", "opened_at": "2026-03-23 09:00:00"}}])
    assert "finance-controller" not in _who(r[0]["approvers"], DATASETS[0])
    assert "finance-controller" in required_approvers(RULES, DATASETS[0], datetime(2026, 3, 23, 9, tzinfo=timezone.utc))


def test_the_compiled_request_rule_refuses_a_malformed_cost_centre():
    compiled = compile_platform(RULES, DATASETS, ROLES)
    script = next(c["f"]["script"] for c in compiled if c["f"]["name"].startswith("Request fields"))
    ok, bad, none = _run(script, [{"fields": {"u_dataset": "gl_actuals", "u_cost_centre": "CC-4120", "cat_item": "x"}},
                                  {"fields": {"u_dataset": "gl_actuals", "u_cost_centre": "CC-12", "cat_item": "x"}},
                                  {"fields": {"cat_item": "x"}}])
    assert ok["errors"] == []
    assert "abort" in bad["errors"]
    assert none["errors"] == [], "a request that is not a data-access request is left alone"
