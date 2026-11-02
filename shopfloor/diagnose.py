"""find_gaps(): the vocabulary checked against the estate. A gap is written in the same terms as its remedy.

Nothing here reads the world generator or the answer key; the scorer does that separately.
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from shopfloor import store
from shopfloor.ingest import APPROVE, Estate

IDLE_DAYS = 90
USAGE_DAYS = 180
# One bar for everything earned on evidence: declared policy here, autonomy in the ledger. It sits above the
# approval rate of ordinary review, so a cell clears it only when approval is close to certain.
POLICY_BOUND = 0.95


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = k / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


# The fewest requests that can clear the bar even if every one was approved. A smaller cell can never be a
# candidate, so stating a smaller minimum would mislead.
POLICY_MIN = next(n for n in range(1, 10000) if wilson_lower(n, n) >= POLICY_BOUND)


def _ts(iso: str | None) -> datetime | None:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def find_gaps(rec: dict, estate: Estate, classes: dict, now: datetime) -> list[dict]:
    gaps: list[dict] = []

    def gap(kind, subject, evidence, proposes, **extra):
        gaps.append({"id": f"gap-{kind}-{len(gaps) + 1}", "gap_kind": kind, "subject": subject,
                     "evidence": [str(e) for e in evidence][:20], "proposes": proposes, **extra})

    # 1. The vocabulary checked against the record: an action with no request fails validation.
    errors = store.check({"actions": rec["actions"], "actors": rec["actors"]})
    orphan_idx = {int(e.split("/actions/")[1].split()[0].split("/")[0]) for e in errors
                  if "/actions/" in e and "'request' is a required property" in e}
    by_actor = defaultdict(list)
    for i in sorted(orphan_idx):
        by_actor[rec["actions"][i]["actor"]].append(rec["actions"][i]["id"])
    for actor, ids in sorted(by_actor.items()):
        gap("orphan_action", actor, ids, "Route this agent's actions through a request (work.request.id).",
            count=len(ids))

    # 2. Actors acting that no registry knows.
    actors = {a["id"]: a for a in rec["actors"]}
    for actor in sorted({a["actor"] for a in rec["actions"]}):
        if not actors.get(actor, {}).get("registered"):
            hosts = [s["resource"]["host.name"] for s in estate.spans if s["attributes"].get("gen_ai.agent.id") == actor]
            armis = [x for x in estate.armis if x["fields"]["display"].lower() in {h.lower() for h in hosts}]
            gap("unregistered_actor", actor, sorted(set(hosts)) + [f"armis:{x['asset_id']}" for x in armis],
                "Register the agent and give it an owner and a passport, or stop it.")

    # 3. Standing access: unexplained by any request (drift), or unused (idle).
    idle_cut = now - timedelta(days=IDLE_DAYS)
    for g in rec["grants"]:
        if not g.get("request"):
            gap("drift", g["id"], [g["id"]], "Revoke, or explain the grant with a request.")
        last = _ts(g.get("last_used_at"))
        if last is None or last < idle_cut:
            gap("idle_privilege", g["id"], [g["id"]], "Revoke the unused grant.",
                last_used_at=g.get("last_used_at"))

    # 4. Customisations: duplicates, dead ones, and what the vocabulary cannot express yet.
    answers = {a["id"]: a for a in classes["answer"]["items"]}
    definitions = [it for it in estate.items if answers.get(it["sys_id"], {}).get("meaning") == "defines_the_work"]
    if len(definitions) > 1:
        for it in definitions:
            gap("duplicate_definition", it["sys_id"], [x["sys_id"] for x in definitions],
                "One work definition (wd-data-access) replaces these catalogue items.", name=it["name"])
    dead = set()
    for u in usage(estate, answers, now):
        if u["executions_180d"] == 0:
            dead.add(u["id"])
            gap("dead_customisation", u["id"], [u["how"]], "Retire it (replay first).", name=u["name"])
    # Dead customisations are retired first; only what is still used tells the vocabulary what it lacks.
    for cid, a in answers.items():
        if cid in dead:
            continue
        if a["proposed_plan"] == "keep" or a["meaning"] == "outside_vocabulary":
            gap("vocabulary", cid, [a["reason"]], "Extend the vocabulary; keep the customisation until then.",
                name=next((c["name"] for c in _named(estate) if c["id"] == cid), cid))

    # 5. Policy candidates: approvals that are a formality, by who asks for what. The evidence is the whole
    # chain of approvals on each request (owner, security, controller), not the owner's alone.
    for key, c in sorted(cells(rec, {u["user_name"]: u.get("title") for u in estate.users.values()}).items(),
                         key=lambda kv: -kv[1]["n"]):
        lb = wilson_lower(c["approved"], c["n"])
        if c["n"] >= POLICY_MIN and lb >= POLICY_BOUND:
            gap("policy_candidate", ":".join(map(str, ("approve", *key))), c["requests"][-5:],
                "Declare this as policy, so the request is not needed.",
                volume=c["n"], approved=c["approved"], lower_bound=round(lb, 3))
    return gaps


def cells(rec: dict, titles: dict[str, str | None], since: str | None = None, until: str | None = None) -> dict:
    """Requests by (requester title, domain, classification, privilege): how many, and how many every approver
    approved. Optionally limited to requests opened in [since, until)."""
    datasets = {d["id"]: d for d in rec["datasets"]}
    by_req = defaultdict(list)
    for t in rec["tasks"]:
        if t["step"] == APPROVE:
            by_req[t["request"]].append(t)
    out: dict = {}
    for r in rec["requests"]:
        d = datasets.get(r.get("dataset"))
        if not d or not by_req.get(r["id"]):
            continue
        if (since and r["requested_at"] < since) or (until and r["requested_at"] >= until):
            continue
        key = (titles.get(r["on_behalf_of"]), d["domain"], d["classification"], r.get("privilege"))
        c = out.setdefault(key, {"n": 0, "approved": 0, "requests": []})
        c["n"] += 1
        c["approved"] += all(t["outcome"]["status"] == "accepted" for t in by_req[r["id"]])
        c["requests"].append(r["id"])
    return out


def _named(estate: Estate) -> list[dict]:
    from shopfloor.classify import customisations
    return customisations(estate)


def usage(estate: Estate, answers: dict, now: datetime) -> list[dict]:
    """How often each customisation acted in the last 180 days, measured from the record."""
    cut = now - timedelta(days=USAGE_DAYS)
    cut_sn = cut.strftime("%Y-%m-%d %H:%M:%S")
    recent = [r for r in estate.ritms if r["opened_at"] >= cut_sn]
    out = []
    for it in estate.items:
        n = sum(1 for r in recent if r["cat_item"] == it["sys_id"])
        out.append({"id": it["sys_id"], "name": it["name"], "executions_180d": n,
                    "how": f"{n} requests through this item since {cut_sn}"})
    for f in estate.fields:
        el = f["element"]
        n = sum(1 for r in recent if r.get(el))
        out.append({"id": f["sys_id"], "name": f"sc_req_item.{el}", "executions_180d": n,
                    "how": f"{n} requests with {el} set since {cut_sn}"})
    for r in estate.customer_rules():
        a = answers.get(r["sys_id"], {})
        bad = _unknown_fields(estate, a.get("effect_table"), a.get("effect_query"))
        if bad:
            n, how = -1, f"effect query names fields that do not exist: {bad}; usage unknown"
        elif a.get("effect_table") and a.get("effect_query"):
            # ^NQ starts a new OR group; the time window has to apply to every group.
            q = "^NQ".join(f"{part}^sys_created_on>={cut_sn}" for part in a["effect_query"].split("^NQ"))
            try:
                n = estate.sn.count(a["effect_table"], q)
                how = f"{n} {a['effect_table']} records match the rule's effect since {cut_sn}"
            except RuntimeError as e:
                n, how = -1, f"effect query failed: {e}"
        else:
            n, how = -1, "no effect query; usage unknown"
        out.append({"id": r["sys_id"], "name": r["name"], "executions_180d": n, "how": how})
    return out


OPERATORS = ["ISNOTEMPTY", "ISEMPTY", "NOT LIKE", "STARTSWITH", "ENDSWITH", "NOT IN", "LIKE", "IN", "!=", ">=", "<=",
             "=", ">", "<", "ON", "BETWEEN"]


def _unknown_fields(estate: Estate, table: str | None, query: str | None) -> list[str]:
    """ServiceNow ignores conditions on fields that do not exist and returns every row, so check first."""
    if not table or not query:
        return []
    bad = []
    for cond in query.replace("^NQ", "^").replace("^OR", "^").split("^"):
        cond = cond.strip()
        if not cond or cond.startswith("ORDERBY"):
            continue
        cut = min((cond.find(op) for op in OPERATORS if cond.find(op) > 0), default=len(cond))
        field = cond[:cut].split(".")[0]
        if field and estate.sn.field_type(table, field) is None:
            bad.append(field)
    return bad
