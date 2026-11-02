"""Read the estate into one record, through the vocabulary.

Sources: the ServiceNow instance (live, Table API) and the simulated Veza, Armis, Moveworks and agent
telemetry fixtures. Nothing here reads the world generator or the answer key.

The scope is the work itself: catalogue items in the "Data Access" category, the requests made through them,
and everything those requests touched.

ServiceNow and Veza records are read through their SSSOM mapping sets: the exact matches in mappings/ say which
field fills which slot, and the slot's range in the vocabulary says how a reference resolves (an Actor by its
user name, a WorkRequest by its number). Close and related matches are transforms, written here and named
after their mapping row. Moveworks and Armis mappings are checked but drive no join in this demo; the
telemetry fixture is read directly.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shopfloor.mappings import crosswalk, fields, flatten
from shopfloor.servicenow import Instance
from shopfloor.vocab import ROOT, view

FIXTURES = ROOT / "data" / "fixtures"
CATEGORY = "Data Access"
APPROVE, PROVISION = "st-approve", "st-provision"
WORK_DEFINITION = "wd-data-access"


def _iso(sn_time: str | None) -> str | None:
    return sn_time.replace(" ", "T") + "Z" if sn_time else None


def _load(rel: str) -> dict:
    return json.loads((FIXTURES / rel).read_text())


SN = crosswalk("servicenow", "contoso-servicenow")
VEZA = crosswalk("veza")
# Fields the transforms (close and related matches) read, beyond the exact matches.
TRANSFORM_FIELDS = {"sc_req_item": ["sys_id", "state", "reassignment_count", "contact_type", "closed_at"],
                    "sysapproval_approver": ["state"], "sc_task": ["state", "reassignment_count"]}


def _fields(table: str) -> list[str]:
    return sorted(set(fields(SN, table)) | set(TRANSFORM_FIELDS.get(table, [])) | {"sys_id"})


def through(table: str, row: dict, classes: tuple[str, ...], refs: dict, walk: list[dict] | None = None) -> dict:
    """One record in the vocabulary's terms, from one ServiceNow row, through the mapping's exact matches. A
    slot whose range is a class resolves through refs[range] (a referenced sys_id -> that record's id); a
    datetime becomes ISO 8601 UTC."""
    sv = view()
    out = {}
    for m in SN if walk is None else walk:
        if m["table"] != table or m["cls"] not in classes or m["slot"] in out:
            continue
        v = row.get(m["field"]) or None
        rng = sv.induced_slot(m["slot"], m["cls"]).range
        if v is not None and rng in refs:
            v = refs[rng].get(v)
        elif v is not None and rng == "datetime":
            v = _iso(v)
        out[m["slot"]] = v
    return {k: v for k, v in out.items() if v is not None}


class Estate:
    """Everything read from the sources, before it becomes a record."""

    def __init__(self, sn: Instance, now: datetime | None = None):
        self.sn = sn
        self.now = now or datetime.now(timezone.utc)
        from shopfloor.seed.world import sys_id
        # The one item generated from the vocabulary is the model's output, not a customisation.
        self.generated_item = sys_id("item", WORK_DEFINITION)
        self.items = [i for i in sn.query("sc_cat_item", f"category.title={CATEGORY}^active=true",
                                          ["sys_id", "name", "short_description", "sys_created_on", "sys_created_by",
                                           "active"]) if i["sys_id"] != self.generated_item]
        every = sn.query("sc_cat_item", f"category.title={CATEGORY}", ["sys_id"])
        item_ids = ",".join(i["sys_id"] for i in every)
        # The mapped fields, plus every custom field the diagnosis measures usage of.
        custom = [f["element"] for f in sn.query("sys_dictionary", "name=sc_req_item^elementSTARTSWITHu_", ["element"])]
        self.ritms = sn.query("sc_req_item", f"cat_itemIN{item_ids}", sorted(set(_fields("sc_req_item")) | set(custom)),
                              limit=100000)
        ritm_ids = {r["sys_id"] for r in self.ritms}
        self.approvals = [a for a in sn.query("sysapproval_approver", "source_table=sc_req_item",
                                              _fields("sysapproval_approver"), limit=100000)
                          if a["sysapproval"] in ritm_ids]
        self.tasks = [t for t in sn.query("sc_task", "request_itemISNOTEMPTY", _fields("sc_task"), limit=100000)
                      if t["request_item"] in ritm_ids]
        people = {r["requested_for"] for r in self.ritms} | {r["opened_by"] for r in self.ritms} | \
                 {a["approver"] for a in self.approvals} | {t["assigned_to"] for t in self.tasks}
        users = sn.query("sys_user", "sys_idIN" + ",".join(sorted(p for p in people if p)),
                         sorted(set(_fields("sys_user")) | {"title", "email"}), limit=10000) if people else []
        self.users = {u["sys_id"]: u for u in users}
        self.rules = sn.query("sys_script", "collection=sc_req_item", [
            "sys_id", "name", "when", "active", "script", "sys_created_on", "sys_created_by", "sys_package.name",
            "action_insert", "action_update"])
        self.fields = sn.query("sys_dictionary", "name=sc_req_item^elementSTARTSWITHu_", [
            "sys_id", "element", "column_label", "internal_type", "sys_created_on", "sys_created_by"])
        self.veza = _load("veza/oaa_payloads.json")["payloads"]
        self.activity = _load("veza/activity.json")["activity"]
        self.armis = _load("armis/assets_search.json")["results"]
        self.moveworks = _load("moveworks/intake.json")["calls"]
        self.spans = _load("telemetry/spans.json")["spans"]
        self.datasets = _load("datasets.json")["datasets"]

    def customer_rules(self) -> list[dict]:
        """Active business rules the customer wrote: in the Global package, not shipped by a ServiceNow plugin, and
        not compiled from the model (those are the model's output, regenerated, never a customisation)."""
        return [r for r in self.rules if (r.get("sys_package.name") or "Global") == "Global" and r["active"] == "true"
                and not r["name"].endswith("(compiled from the model)")]


def _user(estate: Estate, sys_id: str) -> str | None:
    u = estate.users.get(sys_id)
    return u["user_name"] if u else None


def record(estate: Estate) -> dict:
    """The record, in the vocabulary's terms."""
    actors, seen = [], set()

    def actor(name: str, kind: str, registered: bool, display: str | None = None, owner: str | None = None,
              title: str | None = None):
        if name in seen or not name:
            return
        seen.add(name)
        a = {"id": name, "name": display or name, "actor_kind": kind, "registered": registered}
        if owner:
            a["owner"] = owner
        if title:
            a["title"] = title
        actors.append(a)

    # Registry: identities ServiceNow and Veza know. Veza's local_agents are agents; service accounts are users
    # whose ServiceNow record says so.
    veza_agents = {a["id"]: a for p in estate.veza.values() for a in p["applications"][0]["local_agents"]}
    owner_by_email = {u["email"]: u["user_name"] for u in estate.users.values()}
    for u in estate.users.values():
        kind = "agent" if u["user_name"] in veza_agents else (
            "service_account" if "service account" in (u.get("title") or "").lower() else "person")
        owner = None
        if kind == "agent":
            ow = veza_agents[u["user_name"]].get("owners") or []
            owner = owner_by_email.get(ow[0]["external_id"]) if ow else None
        actor(u["user_name"], kind, True, u.get("name"), owner, u.get("title"))
    for p in estate.veza.values():
        for lu in p["applications"][0]["local_users"]:
            actor(lu["name"], "service_account" if lu["name"].startswith("svc") else "person", True)

    datasets = [{"id": d["id"], "name": d["name"], "platform": d["platform"], "classification": d["classification"],
                 "domain": d["domain"], "owner": d["owner"]} for d in estate.datasets]
    for d in datasets:
        actor(d["owner"], "person", True)

    work_definitions = [{"id": WORK_DEFINITION, "name": "Grant access to data", "steps": [
        {"id": APPROVE, "name": "Approve", "risk_class": "medium", "requires_approval": True},
        {"id": PROVISION, "name": "Provision", "risk_class": "high", "requires_approval": False}]}]
    for it in estate.items:
        work_definitions.append({"id": it["sys_id"], "name": it["name"]})

    # Grants as Veza holds them, with last use from the activity export (the latest use of any grant still held).
    used: dict[tuple, str | None] = {}
    history: dict[tuple, list[dict]] = {}
    for a in estate.activity:
        key = (a["identity"], a["resource"], a["permission"])
        history.setdefault(key, []).append(a)
        if not a.get("revoked_at"):
            used[key] = max(filter(None, [used.get(key), a["last_used_at"]]), default=None)
    grant_paths = {m["slot"]: m["path"] for m in VEZA if m["cls"] == "Grant"}
    grants = []
    for platform, p in estate.veza.items():
        for row in flatten(p, list(grant_paths.values())):
            g = {slot: row.get(path) for slot, path in grant_paths.items()}
            if not g.get("dataset"):
                continue  # a permission on the whole application, not a grant on a dataset
            key = (g["actor"], g["dataset"], g["privilege"])
            grants.append({"id": f"{platform}:{g['actor']}:{g['dataset']}:{g['privilege']}", **g,
                           "held_in": "veza", "last_used_at": _iso(used.get(key))})

    # Requests, approvals and provisioning tasks from ServiceNow, through the mapping.
    chat = {c["ticket"]: c for c in estate.moveworks}
    refs = {"Actor": {sid: u["user_name"] for sid, u in estate.users.items()},
            "WorkRequest": {r["sys_id"]: r["number"] for r in estate.ritms}}
    requests, tasks = [], []
    by_ritm = {r["sys_id"]: r for r in estate.ritms}
    for r in estate.ritms:
        req = through("sc_req_item", r, ("WorkRequest", "AccessRequest", "ContosoAccessRequest"), refs)
        # work:WorkRequest.channel relatedMatch sc_req_item.contact_type
        req["channel"] = "moveworks" if r["number"] in chat else (r.get("contact_type") or "portal")
        requests.append(req)
    for a in estate.approvals:
        t = through("sysapproval_approver", a, ("TaskRecord",), refs)
        # work:Outcome.status closeMatch sysapproval_approver.state: approved -> accepted, otherwise failed (deny).
        approved = a["state"] == "approved"
        tasks.append({**t, "step": APPROVE, "decision": {"effect": "allow" if approved else "deny",
                                                         "decided_by": "approver"},
                      "outcome": {"status": "accepted" if approved else "failed"}})
    for t in estate.tasks:
        r = by_ritm[t["request_item"]]
        who = refs["Actor"].get(r["requested_for"])
        # work:Outcome.status relatedMatch veza:activity.revoked_at and sc_req_item.reassignment_count: the grant
        # this task made is the latest the authority system recorded up to the task's close; revoked means
        # reversed, whatever the person holds today. Only the history can tell: a later request re-grants the key.
        made = [a for a in history.get((who, r.get("u_dataset"), r.get("u_privilege")), [])
                if a["granted_at"] <= (t.get("closed_at") or r.get("closed_at") or "")]
        grant = max(made, key=lambda a: a["granted_at"]) if made else None
        if grant is None or grant.get("revoked_at"):
            status = "reversed"  # fulfilled, but the authority system shows the grant gone
        elif int(r.get("reassignment_count") or 0) > 0:
            status = "reassigned"
        else:
            status = "accepted"
        tasks.append({**through("sc_task", t, ("TaskRecord",), refs), "step": PROVISION,
                      "on_behalf_of": who, "outcome": {"status": status}})

    # Which grants a fulfilled request explains.
    req_for_grant = {}
    for r in estate.ritms:
        if r.get("state") == "3":
            req_for_grant[(_user(estate, r["requested_for"]), r.get("u_dataset"), r.get("u_privilege"))] = r["number"]
    for g in grants:
        rq = req_for_grant.get((g["actor"], g["dataset"], g["privilege"]))
        if rq:
            g["request"] = rq

    # Observed actions from agent telemetry. Hosts come from the span's resource; Armis knows the hosts.
    actions = []
    for s in estate.spans:
        a = s["attributes"]
        agent = a.get("gen_ai.agent.id")
        actor(agent, "agent", agent in veza_agents or agent in {u["user_name"] for u in estate.users.values()})
        act = {"id": s["span_id"], "actor": agent, "target_system": a.get("db.namespace"),
               "operation": a.get("gen_ai.tool.name"), "at": _iso(s["start_time"]), "source": "otel"}
        if a.get("work.request.id"):
            act["request"] = a["work.request.id"]
        actions.append(act)

    return {"work_definitions": work_definitions, "actors": actors, "datasets": datasets, "grants": grants,
            "requests": requests, "tasks": tasks, "actions": actions}


def write(rec: dict, path: Path = ROOT / "var" / "record.json") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1, sort_keys=True))
    return path
