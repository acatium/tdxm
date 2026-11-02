"""The demo, step by step. Each step writes its evidence to var/; `make archive` copies it to results/run/.

Two phases, with a person between them:
  propose: diagnose, clean-up, declared policy and autonomy, each written as a proposal (var/proposals.yaml);
  a person writes data/confirmations.yaml;
  apply:   only what was confirmed is applied, then the run, the checks and the close.

Usage: python -m shopfloor.run <step> [--refresh]
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone

import yaml

from shopfloor import classify, cleanup, confirm, diagnose, export, ingest, ledger, live, ocsf, policy, score, store
from shopfloor.mappings import read_sssom
from shopfloor.servicenow import from_env
from shopfloor.vocab import ROOT

# The demo's "today". Fixed, so a rerun on another day gives the same answer.
NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
RESULTS = ROOT / "results"
VAR = ROOT / "var"
# Declared policy is derived from the first year and measured on the second.
SPLIT = "2025-11-01T00:00:00Z"


def diagnose_step(refresh: bool = False) -> dict:
    sn = from_env()
    if sn.count("sc_cat_item", "name=Request access to data^active=true"):
        raise SystemExit("The instance has already been cleaned up. Start from the seeded state: make demo.")
    estate = ingest.Estate(sn, NOW)
    rec = ingest.record(estate)
    ingest.write(rec)
    classes = classify.classify(estate, refresh=refresh)
    gaps = diagnose.find_gaps(rec, estate, classes, NOW)
    scores = score.score(gaps)
    usage = diagnose.usage(estate, {a["id"]: a for a in classes["answer"]["items"]}, NOW)

    # The record, loaded through the vocabulary (gaps included), for the later steps and the Ossie model.
    con = store.connect(VAR / "record.duckdb", fresh=True)
    loaded = store.load(con, {**rec, "gaps": [{k: g[k] for k in ("id", "gap_kind", "subject", "evidence", "proposes")}
                                              for g in gaps]}, validate_first=False)

    # One report, two lenses: OCSF for security, checked by OCSF's validator (one per kind of gap).
    lenses = {}
    for kind in sorted({g["gap_kind"] for g in gaps}):
        g = next(x for x in gaps if x["gap_kind"] == kind)
        event = ocsf.project("Gap", {k: g[k] for k in ("id", "gap_kind", "subject", "proposes")})
        lenses[kind] = ocsf.validate(event)["error_count"]
    (VAR / "gaps.json").write_text(json.dumps(gaps, indent=1))
    (VAR / "gaps.ocsf.jsonl").write_text("\n".join(
        json.dumps(ocsf.project("Gap", {k: g[k] for k in ("id", "gap_kind", "subject", "proposes")})) for g in gaps))
    summary = {"records": {k: len(v) for k, v in rec.items()}, "loaded": loaded,
               "gaps": dict(Counter(g["gap_kind"] for g in gaps)), "score": scores, "ocsf_errors": lenses,
               "usage": usage, "classification_model": classes.get("model")}
    (VAR / "diagnosis.json").write_text(json.dumps(summary, indent=1, default=str))
    return summary


def _context(refresh: bool = False):
    sn = from_env()
    estate = ingest.Estate(sn, NOW)
    rec = ingest.record(estate)
    classes = classify.classify(estate, refresh=refresh)
    answers = {a["id"]: a for a in classes["answer"]["items"]}
    usage = diagnose.usage(estate, answers, NOW)
    return sn, estate, rec, classes, usage


def _roles(rec: dict) -> list[dict]:
    return [{"id": cleanup.slug(t), "name": t} for t in sorted({a.get("title") for a in rec["actors"] if a.get("title")})]


def cleanup_step(apply: bool = True, refresh: bool = False) -> dict:
    sn, estate, rec, classes, usage = _context(refresh)
    result = cleanup.run(estate, rec, classes, usage, refresh=refresh)
    (VAR / "cleanup.json").write_text(json.dumps(result, indent=1, default=str))
    if apply:
        result["applied"] = cleanup.apply_plan(sn, result)
        (VAR / "cleanup.json").write_text(json.dumps(result, indent=1, default=str))
    return result


def after_step() -> dict:
    """The record's own checks after clean-up: what remains is the residue."""
    sn, estate, rec, classes, usage = _context()
    gaps = diagnose.find_gaps(rec, estate, classes, NOW)
    out = {"gaps": dict(Counter(g["gap_kind"] for g in gaps)),
           "customisation_gaps": [{"kind": g["gap_kind"], "name": g.get("name"), "subject": g["subject"]}
                                  for g in gaps if g["gap_kind"] in ("duplicate_definition", "dead_customisation",
                                                                     "vocabulary")],
           "active_items": [i["name"] for i in estate.items], "generated_item": estate.generated_item, "active_rules": [r["name"] for r in estate.customer_rules()],
           "fields": [f["element"] for f in estate.fields]}
    (VAR / "after.json").write_text(json.dumps(out, indent=1))
    return out


def policy_step() -> dict:
    """Declared policy: derived from year one, measured on year two, and only those measured policies proposed.
    Only the confirmed ones are compiled."""
    rec = json.loads((VAR / "record.json").read_text())
    titles = {a["id"]: a.get("title") for a in rec["actors"]}
    bar = {"lower_bound": diagnose.POLICY_BOUND, "min_requests": diagnose.POLICY_MIN, "cap": policy.CAP}
    try:
        rules = policy.rules_proved(json.loads((VAR / "cleanup.json").read_text()))
    except ValueError as e:
        out = {"bar": bar, "refused": str(e), "derived": [], "measured": {}, "proposals": [], "confirmed": [],
               "immuta": [], "immuta_errors": [], "veza_roles": {}, "policy_errors": []}
        (VAR / "policy.json").write_text(json.dumps(out, indent=1))
        (VAR / "veza_policy.json").write_text("{}")
        (VAR / "policy_proposals.json").write_text("[]")
        return out
    table = diagnose.cells(rec, titles, until=SPLIT)
    derived = policy.derive(table, rules)
    measured = {"avoidable": policy.avoidable(rec, derived, titles, since=SPLIT),
                "answer_key": score.policy_key_share(rec, since=SPLIT),
                "granted_beyond_key": score.beyond_key(rec, derived, since=SPLIT)}
    props = policy.proposals(derived, rec["datasets"], table, measured["avoidable"])
    confirmed, decided = policy.confirmed(props, confirm.load())
    out = {"bar": bar,
           "derived_from": f"requests before {SPLIT}", "measured_on": f"requests from {SPLIT}",
           "derived": [{k: p[k] for k in ("id", "max_classification")} for p in derived],
           "measured": measured,
           "proposals": decided, "confirmed": confirmed,
           "policy_errors": policy.validate_policies(derived, _roles(rec))}
    immuta = policy.compile_immuta(confirmed)
    veza = policy.compile_veza(confirmed, rec["datasets"]) if confirmed else {}
    out |= {"immuta": immuta, "immuta_errors": policy.check_immuta(immuta),
            "veza_roles": {k: len(v["applications"][0]["local_roles"]) for k, v in veza.items()}}
    (VAR / "policy.json").write_text(json.dumps(out, indent=1))
    (VAR / "veza_policy.json").write_text(json.dumps(veza, indent=1))
    (VAR / "policy_proposals.json").write_text(json.dumps(props, indent=1))
    return out


def proposals_step() -> dict:
    """Everything waiting for a person, in one file, with a template for the confirmations."""
    rec = json.loads((VAR / "record.json").read_text())
    cu = json.loads((VAR / "cleanup.json").read_text())
    props = [cu["proposal"]] + json.loads((VAR / "policy_proposals.json").read_text())
    cap = live.provisioning_capability(rec)
    confirmations = confirm.load()
    while ledger.apply_confirmed(cap, confirmations, "now"):
        pass
    up = ledger.propose(cap)
    if up:
        props.append(up)
    decided = {c["id"]: c["verdict"] for c in confirmations}
    rows = [{k: p.get(k) for k in ("id", "change_kind", "summary", "needs")} | {"verdict": decided.get(p["id"])}
            for p in props]
    (VAR / "proposals.yaml").write_text(yaml.safe_dump({"proposals": rows}, sort_keys=False, width=110))
    (VAR / "confirmations.template.yaml").write_text(confirm.template([p for p in props if p["id"] not in decided]))
    return {"proposals": rows, "open": sum(1 for r in rows if r["verdict"] is None)}


def scenario_step() -> dict:
    """SCENARIO ONLY. Write the stand-in process owner's confirmations of every open proposal, labelled as such.
    In a deployment a person writes data/confirmations.yaml; this step exists so the demo can run unattended."""
    rows = yaml.safe_load((VAR / "proposals.yaml").read_text())["proposals"]
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = ["# SCENARIO DATA, not a real person's decision. Written by `make scenario`.",
             "# In the demo, Contoso's process owner is a scripted stand-in, like the approvers in chat and the security",
             "# stop. The mechanism is what the demo shows: without a confirmation of a proposal's exact id, nothing is",
             "# applied. In a deployment a person writes this file.",
             "confirmations:"]
    for p in rows:
        lines += [f"- id: {p['id']}", f"  change_kind: {p['change_kind']}", "  verdict: approve",
                  "  decided_by: contoso.process.owner (scenario stand-in)", f"  decided_at: {at}",
                  "  reason: Scenario stand-in for the process owner's decision.", ""]
    confirm.CONFIRMATIONS.write_text("\n".join(lines))
    return {"confirmed": len(rows), "at": at}


def enforcement_step() -> dict:
    """After clean-up, the platform enforces the model on its own, through its front door and around it: an
    order through the generated item, and a request inserted directly, each get the approvals the model
    requires; an order with a malformed cost centre is refused. None of it goes through the gate."""
    sn = from_env()
    rec = json.loads((VAR / "record.json").read_text())
    cu = json.loads((VAR / "cleanup.json").read_text())
    if not cu.get("applied", {}).get("applied"):
        return {"skipped": "clean-up not applied (no confirmation)"}
    users = {u["user_name"]: u["sys_id"] for u in sn.query("sys_user", "user_nameIN" + ",".join(
        sorted({a["id"] for a in rec["actors"]})), ["sys_id", "user_name"], limit=1000)}
    names = {v: k for k, v in users.items()}
    titles = {a["id"]: a.get("title") for a in rec["actors"]}
    requester = sorted(a["id"] for a in rec["actors"] if a.get("title") == "Credit analyst")[0]
    ds = next(d for d in rec["datasets"] if d["id"] == "counterparty_exposure")
    item = cu["applied"]["new_item"]
    expected = ["owner", "security-analyst"]

    def asked(ritm_id: str) -> list[str]:
        rows = sn.query("sysapproval_approver", f"sysapproval={ritm_id}", ["approver"])
        return sorted({"owner" if names.get(r["approver"]) == ds["owner"] else cleanup.slug(titles.get(names.get(r["approver"])))
                       for r in rows})

    variables = {"dataset": ds["id"], "privilege": "read", "cost_centre": "CC-4120", "justification": "Enforcement check"}
    out = {"dataset": ds["id"], "expected": expected}
    live.cleanup_live(sn)
    try:
        ordered = sn.order(item, variables, users[requester])
        out["catalogue_order"] = {"approvals_asked_by_platform": asked(ordered["sys_id"])}
        direct = sn.insert("sc_req_item", {"number": "RITM3000001", "cat_item": item, "requested_for": users[requester],
                                           "opened_by": users[requester], "u_dataset": ds["id"], "u_privilege": "read",
                                           "u_cost_centre": "CC-4120", "short_description": "Direct insert (enforcement check)"})
        out["direct_insert"] = {"approvals_asked_by_platform": asked(direct["sys_id"])}
        try:
            sn.order(item, variables | {"cost_centre": "CC-12"}, users[requester])
            out["malformed_cost_centre"] = {"refused": False}
        except RuntimeError as e:
            out["malformed_cost_centre"] = {"refused": True, "how": str(e)[:200]}
    finally:
        live.cleanup_live(sn)
    out["ok"] = (out["catalogue_order"]["approvals_asked_by_platform"] == expected
                 and out["direct_insert"]["approvals_asked_by_platform"] == expected
                 and out["malformed_cost_centre"]["refused"])
    (VAR / "enforcement.json").write_text(json.dumps(out, indent=1))
    return out


def perturb_step() -> dict:
    """The defence does not depend on the agent being right. Seed errors into the agent's translation; every one
    must hold the whole clean-up."""
    import copy
    _, estate, rec, classes, usage = _context()
    decl = cleanup.declare(estate, classes)["answer"]
    hist = cleanup.history(estate, rec)

    def rule(d, pred):
        return next(r for r in d["approval_rules"] if pred(r))

    def drop_window(d):
        rule(d, lambda r: r.get("year_end_close_days")).pop("year_end_close_days")

    def shrink_window(d):
        rule(d, lambda r: r.get("year_end_close_days"))["year_end_close_days"] = 3

    def drop_classification(d):
        rule(d, lambda r: r.get("min_classification")).pop("min_classification")

    def wrong_role(d):
        rule(d, lambda r: r.get("min_classification"))["approver_role"] = "finance-controller"

    def miss_a_rule(d):
        s = next(s for s in d["source_rules"] if s.get("approval_rule") and
                 rule(d, lambda r: r["id"] == s["approval_rule"]).get("year_end_close_days"))
        s["approval_rule"] = None

    out = []
    for f in (drop_window, shrink_window, drop_classification, wrong_role, miss_a_rule):
        d = copy.deepcopy(decl)
        f(d)
        r = cleanup.decide(cleanup.plan(estate, classes, usage), hist, d)
        statuses = {s["status"] for s in r["plan"]}
        out.append({"error": f.__name__, "full_model_diffs": r["full_model_diffs"], "statuses": sorted(statuses),
                    "held": statuses <= {"held", "kept"}})
    result = {"perturbations": out, "all_held": all(x["held"] for x in out)}
    (VAR / "perturb.json").write_text(json.dumps(result, indent=1))
    return result


def live_step() -> dict:
    sn = from_env()
    live.cleanup_live(sn)  # a previous live run's request is not history
    estate = ingest.Estate(sn, NOW)
    rec = ingest.record(estate)
    br = json.loads((VAR / "policy.json").read_text())
    cu = json.loads((VAR / "cleanup.json").read_text())
    held = {s["id"] for s in cu["plan"] if s["status"] == "held"}
    by_rule = {s["rule"]: s for s in cu["declarations"]["source_rules"]}
    rules = {r["id"]: r for r in cu["declarations"]["approval_rules"]}
    # Approval rules in force: every declared one. A held rule is still active on the platform, so the model
    # keeps it too; nothing the platform enforces is dropped.
    in_force = [rules[s["approval_rule"]] for rid, s in by_rule.items() if s.get("approval_rule") in rules]
    item = cu.get("applied", {}).get("new_item")
    if not item:
        raise SystemExit("Clean-up was not applied: confirm it in data/confirmations.yaml, then make apply.")
    out = live.run(sn, rec, br["confirmed"], in_force, item)
    out["held_rules_kept"] = sorted(held)
    (VAR / "live.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def integration_step() -> dict:
    products = {"ServiceNow": "servicenow", "Veza": "veza", "Armis": "armis", "Moveworks": "moveworks"}
    rows = {p: len(read_sssom(ROOT / "mappings" / f"{f}.sssom.tsv")) for p, f in products.items()}
    out = {"mapping_rows": rows, "read_through_mappings": ["ServiceNow", "Veza"],
           "checked_not_used": ["Armis", "Moveworks"]}
    (VAR / "integration.json").write_text(json.dumps(out, indent=1))
    return out


def close_step(ask_agent: bool = True) -> dict:
    rec = json.loads((VAR / "record.json").read_text())
    rec = {k: v for k, v in rec.items()}
    export.write(rec)
    v = export.stock_validate()
    errors = [line for line in v.stdout.splitlines() if line.startswith("[ERROR]")]
    orphan_errors = [e for e in errors if "'request' is a required property in /actions/" in e]
    orphans = sum(1 for a in rec["actions"] if not a.get("request"))
    out = {"stock_validate": {
        "tool": "linkml-validate 1.12.0 from PyPI, isolated environment, no code from this repository",
        "errors": len(errors), "orphan_action_errors": len(orphan_errors), "orphan_actions_in_record": orphans,
        "only_orphans": len(errors) == len(orphan_errors) == orphans, "first": errors[:3]}}
    if ask_agent:
        a = export.outside_agent()
        gaps = json.loads((VAR / "gaps.json").read_text())
        ours = {g["subject"] for g in gaps if g["gap_kind"] == "policy_candidate"}
        theirs = {":".join(["approve", c["requester_title"], c["domain"], c["classification"], c["privilege"]])
                  for c in (a["answer"] or {}).get("candidates", [])}
        out["outside_agent"] = {**a, "matches_diagnosis": ours == theirs, "only_ours": sorted(ours - theirs),
                                "only_theirs": sorted(theirs - ours)}
    (VAR / "close.json").write_text(json.dumps(out, indent=1, default=str))
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "diagnose":
        s = diagnose_step(refresh="--refresh" in sys.argv)
        print(json.dumps({k: s[k] for k in ("records", "gaps", "ocsf_errors")}, indent=1))
        for kind, sc in s["score"].items():
            print(f"{kind:22} expected {sc['expected']:4} found {sc['found']:4} "
                  f"precision {sc['precision']:.3f} recall {sc['recall']:.3f}")
    elif cmd == "cleanup":
        r = cleanup_step(apply="--no-apply" not in sys.argv)
        print(json.dumps({k: r[k] for k in ("replayed", "full_model_diffs", "summary")}, indent=1))
        for st in r["plan"]:
            print(f"{st['status']:9} {st['plan']:21} {st['usage_180d']:5} {st['kind']:15} {st['name']}")
    elif cmd == "after":
        print(json.dumps(after_step(), indent=1))
    elif cmd == "policy":
        r = policy_step()
        print(json.dumps({k: r[k] for k in ("bar", "derived", "measured", "proposals", "policy_errors",
                                              "immuta_errors", "veza_roles")}, indent=1))
    elif cmd == "proposals":
        r = proposals_step()
        print(yaml.safe_dump(r, sort_keys=False, width=110))
        print(f"{r['open']} open. Template: var/confirmations.template.yaml. A person writes data/confirmations.yaml.")
    elif cmd == "scenario":
        print(json.dumps(scenario_step(), indent=1))
    elif cmd == "enforcement":
        print(json.dumps(enforcement_step(), indent=1))
    elif cmd == "perturb":
        print(json.dumps(perturb_step(), indent=1))
    elif cmd == "live":
        r = live_step()
        print(json.dumps({k: r[k] for k in ("request", "chain", "otel", "record_conforms")}, indent=1, default=str))
        print(json.dumps({"platform_approvals": r["platform_approvals"], "ocsf_errors": r["stop"]["ocsf_errors"],
                          "changes": [(c["from_level"], c["to_level"], c["reason"]) for c in r["ledger"]["changes"]],
                          "declared_policy": r["declared_policy"]["decision"]}, indent=1))
    elif cmd == "integration":
        print(json.dumps(integration_step(), indent=1))
    elif cmd == "close":
        r = close_step(ask_agent="--no-agent" not in sys.argv)
        print(json.dumps({k: (v if k != "outside_agent" else {x: v[x] for x in ("matches_diagnosis", "only_ours",
                          "only_theirs", "cost_usd", "turns")}) for k, v in r.items()}, indent=1))
