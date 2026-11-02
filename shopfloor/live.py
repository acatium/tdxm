"""Step 6, the run: two new requests arrive through Moveworks (simulated) on the cleaned-up instance.

1. One a confirmed declared policy covers: the gate allows it at once and no ticket is created.
2. One outside policy: a request is created live on the instance. The platform itself asks for the approvals,
   through the rules compiled from the model; the gate, reading the same model, must name the same approvers.
   The approvers' answers are scripted: the script stands in for people answering chat cards, and every
   event it writes says so. The access agent provisions, but a simulated security stop halts the step first;
   the operator's card and the OCSF event are rendered from the one decision. Security clears it (scripted)
   and the step completes, live.

Around it, the ledger: the access agent's provisioning capability starts at assist and rises only by promotions
a person confirmed in data/confirmations.yaml. A planted breach afterwards demotes it at once. Events are
hash-chained and the head hash is anchored in the request's work notes on the instance; the tamper check
rebuilds the chain after an edit and verifies it against that anchor.
"""

SCRIPTED = "script (stands in for a person)"

import json
from datetime import datetime, timedelta, timezone

from shopfloor import confirm, gate, ledger, ocsf, otel, store, validators
from shopfloor.cleanup import slug
from shopfloor.generate import GEN
from shopfloor.ingest import APPROVE, PROVISION
from shopfloor.seed.world import sys_id
from shopfloor.servicenow import Instance
from shopfloor.vocab import ROOT

LIVE_PREFIX = "RITM2"
AGENT = "svc.access.agent"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sn_time(iso: str) -> str:
    return iso.replace("T", " ").replace("Z", "")


def card(event: dict, decision: dict, actions: list[str]) -> dict:
    """The chat lens: the same reason, rendered as a card. Decide in chat; record in the execution layer."""
    return {"surface": "moveworks", "title": f"Work {event['kind']}: {event['request']}",
            "text": decision["reason"], "rule": decision["rule"], "decided_by": decision["decided_by"],
            "actions": [{"label": a.replace("_", " ").capitalize(), "value": a} for a in actions],
            "context": {"work.request.id": event["request"], "event": event["id"]}}


def cleanup_live(sn: Instance) -> int:
    """Remove what the demo itself ordered: every request through the generated item (history never used it),
    and any request it inserted directly."""
    item = sys_id("item", "wd-data-access")
    ritms = sn.query("sc_req_item", f"cat_item={item}^ORnumberSTARTSWITH{LIVE_PREFIX}^ORnumberSTARTSWITHRITM3",
                     ["sys_id", "request"])
    for r in ritms:
        sn.delete_where("sysapproval_approver", f"sysapproval={r['sys_id']}")
        sn.delete_where("sc_task", f"request_item={r['sys_id']}")
        sn.delete("sc_req_item", r["sys_id"])
    for req in {r["request"] for r in ritms if r.get("request")}:
        sn.delete_where("sc_request", f"sys_id={req}")
    return len(ritms)


def provisioning_capability(rec: dict) -> ledger.Capability:
    """The access agent's capability on the provision step, with history as its evidence. It starts at assist."""
    cap = ledger.Capability(f"cap-{AGENT}-{PROVISION}", AGENT, PROVISION)
    for t in sorted((t for t in rec["tasks"] if t["step"] == PROVISION and t["actor"] == AGENT),
                    key=lambda t: t["ended_at"] or ""):
        ledger.observe(cap, t["id"], t["outcome"]["status"] == "accepted")
    return cap


def run(sn: Instance, rec: dict, policies: list[dict], approval_rules: list[dict], item_id: str) -> dict:
    cleanup_live(sn)
    users = {u["user_name"]: u for u in sn.query(
        "sys_user", "user_nameIN" + ",".join(sorted({a["id"] for a in rec["actors"]})),
        ["sys_id", "user_name", "title", "email"], limit=1000)}
    titles = {k: v.get("title") for k, v in users.items()}
    datasets = {d["id"]: d for d in rec["datasets"]}
    actors = {a["id"]: a for a in rec["actors"]}
    events, tasks, changes, spans, cards = [], [], [], [], []
    stops: list[dict] = []

    def event(kind, request, **kw):
        e = {"id": f"ev-{len(events) + 1:03d}", "kind": kind, "at": _now(), "request": request, **kw}
        events.append(e)
        return e

    # --- The ledger, before the run: promotions a person confirmed, one rung at a time ------------------------
    cap = provisioning_capability(rec)
    confirmations = confirm.load()
    while (promoted := ledger.apply_confirmed(cap, confirmations, _now())):
        changes.append(promoted)
        event("promoted", None, actor=AGENT, reason=f"{promoted['reason']} Confirmed: {promoted['confirmation']}.",
              source="ledger")
    open_proposal = ledger.propose(cap)

    quants = [u for u, t in titles.items() if t == "Quantitative researcher"]
    requester = sorted(quants)[0]
    role = slug(titles[requester])

    # --- Request 1: covered by declared policy -> no ticket -----------------------------------------------
    r1 = {"id": f"mw-{sys_id('live', 1)[:8]}", "requested_by": requester, "on_behalf_of": requester,
          "requested_at": _now(), "channel": "moveworks", "dataset": "market_data_eod", "privilege": "read",
          "justification": "Back-testing a pricing model", "cost_centre": "CC-4120", "work_definition": "wd-data-access"}
    d1 = gate.decide(APPROVE, r1, datasets["market_data_eod"], actors[AGENT], role=role, policies=policies,
                     approval_rules=approval_rules, capability=None, stops=stops, approvals=set())
    event("requested", r1["id"], actor=requester, source="moveworks", via="chat")
    event("decided", r1["id"], actor=AGENT, reason=d1["reason"], source="gate")
    declared = {"request": r1, "decision": d1, "ticket_created": d1["effect"] != "allow"}

    # --- Request 2: outside policy -> a live request ---------------------------------------------------------
    r2 = {"requested_by": requester, "on_behalf_of": requester, "requested_at": _now(), "channel": "moveworks",
          "dataset": "client_master", "privilege": "read", "justification": "Counterparty mapping for the model",
          "cost_centre": "CC-4120", "work_definition": "wd-data-access"}
    errors = store.check({"requests": [{**r2, "id": "pending"}]})
    if errors:
        raise ValueError(f"request does not conform to the vocabulary: {errors}")
    # Moveworks orders the generated item through the Service Catalog API, as a person would in the portal.
    ritm = sn.order(item_id, {"dataset": r2["dataset"], "privilege": r2["privilege"], "cost_centre": r2["cost_centre"],
                              "justification": r2["justification"]}, users[requester]["sys_id"])
    number = ritm["number"]
    r2["id"] = number
    event("requested", number, actor=requester, source="moveworks", via="chat")
    ds = datasets[r2["dataset"]]
    approvals: set[str] = set()
    d = gate.decide(APPROVE, r2, ds, actors[AGENT], role=role, policies=policies, approval_rules=approval_rules,
                    capability=None, stops=stops, approvals=approvals)
    event("decided", number, actor=AGENT, reason=d["reason"], source="gate")
    needed = [x.strip() for x in d["reason"].split(":", 1)[1].rstrip(".").split(",")] if d["effect"] == "checkpoint" else []
    # The platform asked for approvals on insert, through the rules compiled from the model. Read them back.
    platform_rows = sn.query("sysapproval_approver", f"sysapproval={ritm['sys_id']}", ["sys_id", "approver", "state"])
    names = {u["sys_id"]: u["user_name"] for u in users.values()}
    platform_roles: dict[str, list[dict]] = {}
    for row in platform_rows:
        who = names.get(row["approver"])
        key = "owner" if who == ds["owner"] else slug(titles.get(who))
        platform_roles.setdefault(key, []).append(row | {"user_name": who})
    platform = {"approvals_created": len(platform_rows), "roles": sorted(platform_roles),
                "matches_gate": sorted(platform_roles) == sorted(needed)}
    for who in needed:
        rows = platform_roles.get(who, [])
        if not rows:
            raise RuntimeError(f"The platform did not ask {who} to approve {number}; enforcement is not on the platform.")
        first, rest = rows[0], rows[1:]
        e = event("decided", number, actor=first["user_name"], reason=f"Approval requested from {who} by the platform.",
                  source="servicenow")
        cards.append(card(e, {"reason": f"{requester} asks to read {ds['name']} ({ds['classification']}): "
                                        f"{r2['justification']}.", "rule": "approval_rules", "decided_by": "gate"},
                          ["approve", "reject"]))
        sn.update("sysapproval_approver", first["sys_id"], {"state": "approved", "comments": f"Approved: {SCRIPTED}"})
        for other in rest:  # any one of the role approves
            sn.update("sysapproval_approver", other["sys_id"], {"state": "not_required"})
        event("approved", number, actor=first["user_name"], reason=f"Approved in chat ({SCRIPTED}).", source=SCRIPTED,
              via="chat")
        approvals.add(who)
        tasks.append({"id": first["sys_id"], "request": number, "step": APPROVE, "actor": first["user_name"],
                      "autonomy_level": "assist", "decision": {"effect": "allow", "rule": "approval_rules",
                                                               "decided_by": first["user_name"]},
                      "outcome": {"status": "accepted"}})
    d = gate.decide(APPROVE, r2, ds, actors[AGENT], role=role, policies=policies, approval_rules=approval_rules,
                    capability=None, stops=stops, approvals=approvals)
    event("decided", number, actor=AGENT, reason=d["reason"], source="gate")

    # --- Provision: security stops it first ---------------------------------------------------------------
    stop = {"request": number, "rule": "device-posture", "decided_by": "soc",
            "reason": f"{requester}'s workstation failed device posture (Armis risk: high). Hold restricted "
                      "grants until it is remediated."}
    stops.append(stop)
    task = sn.insert("sc_task", {"request_item": ritm["sys_id"], "assigned_to": users[AGENT]["sys_id"],
                                 "short_description": f"Provision read on {ds['name']}"}, fields="sys_id,number")
    d = gate.decide(PROVISION, r2, ds, actors[AGENT], role=role, policies=policies, approval_rules=approval_rules,
                    capability=cap.as_record(), stops=stops, approvals=approvals)
    stopped = event("stopped", number, task=task["number"], actor="soc", reason=d["reason"], source="soc")
    stop_decision = d
    soc_view = ocsf.project("WorkEvent", stopped, decision=d)
    operator_view = card(stopped, d, ["ask_security", "notify_requester"])
    cards.append(operator_view)
    stop["cleared"] = True
    event("approved", number, task=task["number"], actor="soc", reason=f"Device remediated; hold cleared ({SCRIPTED}).",
          source=SCRIPTED)
    d = gate.decide(PROVISION, r2, ds, actors[AGENT], role=role, policies=policies, approval_rules=approval_rules,
                    capability=cap.as_record(), stops=stops, approvals=approvals)
    event("decided", number, task=task["number"], actor=AGENT, reason=d["reason"], source="gate")
    if d["effect"] == "checkpoint":  # the agent's autonomy needs a person first
        iam = sorted(u for u, t in titles.items() if t == "Access administrator")[0]
        event("approved", number, task=task["number"], actor=iam,
              reason=f"Provisioning approved at the checkpoint ({SCRIPTED}).", source=SCRIPTED, via="chat")
    elif d["effect"] != "allow":
        raise RuntimeError(f"The gate refused provisioning: {d}")
    event("started", number, task=task["number"], actor=AGENT, source="servicenow")
    sn.update("sc_task", task["sys_id"], {"state": "3", "work_notes": "Provisioned by the access agent."})
    sn.update("sc_req_item", ritm["sys_id"], {"state": "3"})
    done = event("completed", number, task=task["number"], actor=AGENT, source="servicenow")
    provision = {"id": task["number"], "request": number, "step": PROVISION, "actor": AGENT, "on_behalf_of": requester,
                 "autonomy_level": cap.autonomy_level, "decision": {k: d[k] for k in ("effect", "rule", "decided_by", "reason")},
                 "outcome": {"status": "accepted"}, "external_ref": task["number"]}
    tasks.append(provision)
    ledger.observe(cap, task["number"], True)

    # --- After the run: a planted breach demotes the agent at once -----------------------------------------
    breach = f"{task['number']} reversed: the grant was revoked within its window by the data owner"
    provision["outcome"] = {"status": "reversed"}
    event("reversed", number, task=task["number"], actor=ds["owner"], reason=breach, source="veza")
    demoted = ledger.demote(cap, _now(), breach)
    if demoted:
        changes.append(demoted)
        event("demoted", None, actor=AGENT, reason=demoted["reason"], source="ledger")

    # --- The record of the run: chain, spans, and each lens checked by its own validator ---------------------
    ledger.chain(events)
    # Anchor the head in a second system: the request's work notes, which the platform journals.
    anchor = ledger.head(events)
    sn.update("sc_req_item", ritm["sys_id"], {"work_notes": f"Work record chain head {anchor} over {len(events)} events."})
    notes = sn.query("sys_journal_field", f"element_id={ritm['sys_id']}^element=work_notes^ORDERBYDESCsys_created_on",
                     ["value"])
    held = next((n["value"].split("chain head ", 1)[1].split()[0] for n in notes if "chain head " in n["value"]), None)
    spans = [otel.span({k: v for k, v in t.items() if k != "id"} | {"id": t["id"]}) for t in tasks]
    span_advice = validators.weaver_live_check(GEN / "otel", spans)
    violations = [a for a in span_advice if a["level"] == "violation" or a["id"] == "undefined_enum_variant"]
    ocsf_result = ocsf.validate(soc_view)
    tampered = json.loads(json.dumps(events))
    tampered[len(tampered) // 2]["reason"] = "edited after the fact"
    ledger.chain(tampered)  # a forger rebuilds the hashes
    record_check = store.check({"events": [{k: v for k, v in e.items() if v is not None} for e in events],
                                "tasks": tasks, "changes": changes, "capabilities": [cap.as_record()]})
    return {
        "declared_policy": declared,
        "request": {"number": number, "ritm": ritm["sys_id"], "task": task["number"]},
        "stop": {"soc_ocsf": soc_view, "operator_card": operator_view,
                 "rendered_from_one_decision": soc_view["finding_info"]["desc"] == operator_view["text"] == stop_decision["reason"],
                 "ocsf_errors": ocsf_result["error_count"]},
        "ledger": {"changes": changes, "capability": cap.as_record()},
        "chain": {"events": len(events), "anchor": anchor, "anchor_on_instance": held,
                  "verify": ledger.verify(events, held), "verify_rebuilt_without_anchor": ledger.verify(tampered),
                  "verify_rebuilt_against_anchor": ledger.verify(tampered, held)},
        "platform_approvals": platform, "open_promotion": open_proposal,
        "otel": {"spans": len(spans), "violations": violations},
        "record_conforms": record_check,
        "events": events, "tasks": tasks, "cards": cards,
    }
