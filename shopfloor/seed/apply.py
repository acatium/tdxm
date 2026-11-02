"""Apply the world to a ServiceNow instance, and reset it. Every planted record has a fixed sys_id derived
from the world, so reset needs no state: it deletes exactly what apply would create.

History is written server-side with business rules off and system fields set, so two years of records land
as they would have been: created when they were created, by whom.

Usage: python -m shopfloor.seed.apply [reset|apply|status]
"""

import json
import sys
import time

from shopfloor.seed.world import World, build, sys_id
from shopfloor.servicenow import Instance, from_env
from shopfloor.vocab import ROOT

CATEGORY_ID = sys_id("category", "data-access")
CHUNK = 400

INSERT_JS = """
var rows = %s;
var n = 0, failed = [];
for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    var g = new GlideRecord(r.t);
    if (g.get(r.id)) { n++; continue; }
    g.initialize();
    g.setNewGuidValue(r.id);
    g.setWorkflow(false);
    g.autoSysFields(false);
    for (var k in r.f) g.setValue(k, r.f[k]);
    if (g.insert()) n++; else failed.push(r.t + ':' + r.id);
}
report('inserted ' + n);
if (failed.length) report('failed ' + failed.slice(0, 5).join(','));
"""

DELETE_JS = """
var ids = %s;
var t = '%s';
var g = new GlideRecord(t);
g.addQuery('sys_id', 'IN', ids.join(','));
g.query();
var n = g.getRowCount();
var d = new GlideRecord(t);
d.addQuery('sys_id', 'IN', ids.join(','));
d.setWorkflow(false);
d.deleteMultiple();
report('deleted ' + n);
"""

FIELD_JS = """
var f = %s;
var d = new GlideRecord('sys_dictionary');
d.addQuery('name', f.name); d.addQuery('element', f.element); d.query();
if (!d.next()) {
    d.initialize();
    d.setNewGuidValue(f.id);
    for (var k in f.rec) d.setValue(k, f.rec[k]);
    d.insert();
}
var b = new GlideRecord('sys_dictionary');
if (b.get(f.id)) { b.autoSysFields(false); b.setWorkflow(false); b.setValue('sys_created_on', f.created); b.setValue('sys_created_by', 'admin'); b.update(); }
report('field ' + f.element);
"""

DROP_FIELD_JS = """
var d = new GlideRecord('sys_dictionary');
d.addQuery('name', 'sc_req_item'); d.addQuery('element', 'IN', '%s'); d.query();
var n = 0; while (d.next()) { d.deleteRecord(); n++; }
report('dropped ' + n);
"""


def _audit(created: str, by: str = "admin") -> dict:
    return {"sys_created_on": created, "sys_updated_on": created, "sys_created_by": by, "sys_updated_by": by,
            "sys_mod_count": "0"}


def rows(w: World) -> list[dict]:
    """Every record to insert, in dependency order. Fields named u_* need the custom fields first."""
    user_names = {u["sys_id"]: u["user_name"] for u in w.users}
    out = []
    for u in w.users:
        out.append({"t": "sys_user", "id": u["sys_id"], "f": {
            "user_name": u["user_name"], "first_name": u["first_name"], "last_name": u["last_name"],
            "email": u["email"], "title": u["title"], "active": "true", **_audit("2023-06-01 09:00:00")}})
    out.append({"t": "sc_category", "id": CATEGORY_ID, "f": {"title": "Data Access", "active": "true",
                                                              **_audit("2019-01-10 09:00:00")}})
    for c in w.customisations:
        if c["kind"] == "catalogue_item":
            out.append({"t": "sc_cat_item", "id": c["sys_id"], "f": {
                "name": c["name"], "short_description": c["name"], "active": "true", "category": CATEGORY_ID,
                **_audit(c["created_on"])}})
    for r in w.requests:
        f = {k: r[k] for k in ("number", "cat_item", "requested_for", "opened_by", "opened_at", "short_description",
                               "description", "u_dataset", "u_privilege", "u_cost_centre",
                               "u_chargeback_amount")}
        f.update(state=str(r["state"]), closed_at=r.get("closed_at", ""), active="false",
                 reassignment_count=str(r.get("reassignment_count", 0)), contact_type=r["channel"],
                 **_audit(r["opened_at"], user_names[r["opened_by"]]))
        f["sys_updated_on"] = r.get("closed_at") or r["opened_at"]
        out.append({"t": "sc_req_item", "id": r["sys_id"], "f": f})
    for a in w.approvals:
        out.append({"t": "sysapproval_approver", "id": a["sys_id"], "f": {
            "sysapproval": a["sysapproval"], "source_table": "sc_req_item", "approver": a["approver"],
            "state": a["state"], **_audit(a["sys_created_on"]), "sys_updated_on": a["sys_updated_on"],
            "sys_updated_by": user_names[a["approver"]]}})
    for t in w.tasks:
        out.append({"t": "sc_task", "id": t["sys_id"], "f": {
            "number": t["number"], "request_item": t["request_item"], "assigned_to": t["assigned_to"],
            "opened_at": t["opened_at"], "closed_at": t["closed_at"], "short_description": t["short_description"],
            "state": str(t["state"]), "active": "false", "reassignment_count": str(t["reassignment_count"]),
            **_audit(t["opened_at"]), "sys_updated_on": t["closed_at"]}})
    return out


def rules(w: World) -> list[dict]:
    out = []
    for c in w.customisations:
        if c["kind"] == "business_rule":
            out.append({"t": "sys_script", "id": c["sys_id"], "f": {**c["record"], **_audit(c["created_on"])}})
    return out


def _chunks(xs, n=CHUNK):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def _insert(sn: Instance, records: list[dict], label: str) -> int:
    total = 0
    for chunk in _chunks(records):
        out = sn.run_script(INSERT_JS % json.dumps(chunk))
        if "failed" in out:
            raise RuntimeError(f"{label}: {out}")
        total += int(out.split("inserted ", 1)[1].split()[0])
    return total


def apply(sn: Instance, w: World | None = None) -> dict:
    w = w or build()
    t0 = time.time()
    hist = rows(w)
    base = [r for r in hist if r["t"] in ("sys_user", "sc_category", "sc_cat_item")]
    _insert(sn, base, "base")
    for c in w.customisations:
        if c["kind"] == "custom_field":
            sn.run_script(FIELD_JS % json.dumps({"id": c["sys_id"], "name": "sc_req_item",
                                                 "element": c["record"]["element"], "rec": c["record"],
                                                 "created": c["created_on"]}))
    history = [r for r in hist if r not in base]
    n = _insert(sn, history, "history")
    _insert(sn, rules(w), "rules")
    return {"inserted": len(base) + n + len(rules(w)), "seconds": round(time.time() - t0, 1)}


def reset(sn: Instance, w: World | None = None) -> dict:
    w = w or build()
    t0 = time.time()
    # What the demo itself created: the live run's requests, and the catalogue item generated from the vocabulary.
    from shopfloor import live
    from shopfloor.cleanup import catalogue_item
    demo = {"live_requests": live.cleanup_live(sn)}
    gen = catalogue_item(CATEGORY_ID)
    for v in gen["variables"]:
        for c in v["choices"]:
            sn.delete_where("question_choice", f"sys_id={c['id']}")
        sn.delete_where("item_option_new", f"sys_id={v['id']}")
    demo["generated_item"] = sn.delete_where("sc_cat_item", f"sys_id={gen['item']['id']}")
    demo["compiled_rules"] = sum(sn.delete_where("sys_script", f"sys_id={sys_id('compiled', k)}")
                                 for k in ("approval-rules", "request-required"))
    by_table: dict[str, list[str]] = {}
    for r in rules(w) + rows(w):
        by_table.setdefault(r["t"], []).append(r["id"])
    deleted = {"demo": demo}
    order = ["sys_script", "sc_task", "sysapproval_approver", "sc_req_item", "sc_cat_item", "sc_category", "sys_user"]
    for t in order:
        n = 0
        for chunk in _chunks(by_table.get(t, []), 1000):
            out = sn.run_script(DELETE_JS % (json.dumps(chunk), t))
            n += int(out.split("deleted ", 1)[1].split()[0])
        deleted[t] = n
    # Anything created on the instance by the demo itself later (the live run) is tagged with the request's
    # correlation and removed by the run's own cleanup, not here.
    fields = [c["record"]["element"] for c in w.customisations if c["kind"] == "custom_field"]
    out = sn.run_script(DROP_FIELD_JS % ",".join(fields))
    deleted["sys_dictionary"] = int(out.split("dropped ", 1)[1].split()[0])
    return {"deleted": deleted, "seconds": round(time.time() - t0, 1)}


COUNT_JS = """
var ids = %s;
var t = '%s';
var g = new GlideAggregate(t);
g.addQuery('sys_id', 'IN', ids.join(','));
g.addAggregate('COUNT');
g.query();
report('count ' + (g.next() ? g.getAggregate('COUNT') : 0));
"""


def status(sn: Instance, w: World | None = None) -> dict:
    w = w or build()
    by_table: dict[str, list[str]] = {}
    for r in rules(w) + rows(w):
        by_table.setdefault(r["t"], []).append(r["id"])
    found = {}
    for t, ids in by_table.items():
        found[t] = sum(int(sn.run_script(COUNT_JS % (json.dumps(c), t)).split("count ", 1)[1])
                       for c in _chunks(ids, 3000))
    fields = {c["record"]["element"]: sn.field_type("sc_req_item", c["record"]["element"]) is not None
              for c in w.customisations if c["kind"] == "custom_field"}
    return {"expected": {t: len(ids) for t, ids in by_table.items()}, "found": found, "fields": fields}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    sn = from_env()
    result = {"reset": reset, "apply": apply, "status": status}[cmd](sn)
    if cmd == "status":
        out = ROOT / "var" / "seed.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
