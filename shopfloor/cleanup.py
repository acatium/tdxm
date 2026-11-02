"""Clean up: plan each customisation, translate what carries meaning into Contoso's model, and replay history
through the model before anything changes on the platform. The record is the test oracle.

retire_customisations() from the adoption-path note, made runnable:
- usage from the record says what is dead (retire first);
- the agent's reading says what the rest means (revert, declare, replace, keep);
- the agent writes declarations as instances of the vocabulary, constrained by the vocabulary's own JSON Schema;
- every change is replayed against history; any change that alters a past decision is held for review.
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from shopfloor import agent, confirm
from shopfloor.ingest import APPROVE, Estate
from shopfloor.vocab import ROOT

DECLARATIONS = ROOT / "data" / "declarations.json"
LEVEL = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


def slug(title: str | None) -> str | None:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") if title else None


def plan(estate: Estate, classes: dict, usage: list[dict]) -> list[dict]:
    answers = {a["id"]: a for a in classes["answer"]["items"]}
    used = {u["id"]: u for u in usage}
    names = {it["sys_id"]: ("catalogue_item", it["name"]) for it in estate.items}
    names |= {f["sys_id"]: ("custom_field", f"sc_req_item.{f['element']}") for f in estate.fields}
    names |= {r["sys_id"]: ("business_rule", r["name"]) for r in estate.customer_rules()}
    out = []
    for cid, (kind, name) in names.items():
        a, u = answers.get(cid, {}), used.get(cid, {})
        n = u.get("executions_180d", -1)
        if n == 0:
            p, why = "retire", "No effect in the record in 180 days."
        else:
            p, why = a.get("proposed_plan", "keep"), a.get("reason", "")
        out.append({"id": cid, "kind": kind, "name": name, "plan": p, "why": why, "usage_180d": n,
                    "meaning": a.get("meaning"), "proposed_by_agent": a.get("proposed_plan"),
                    "target_term": a.get("target_term")})
    return out


def roles(estate: Estate) -> list[dict]:
    titles = {(slug(u["title"]), u["title"]) for u in estate.users.values() if u.get("title")}
    return [{"id": i, "name": t} for i, t in sorted(titles)]


def declare(estate: Estate, classes: dict, refresh: bool = False) -> dict:
    """The agent writes each rule that carries meaning as an instance of Contoso's model. Its output must
    validate against the JSON Schema generated from the vocabulary."""
    rules = {r["sys_id"]: r for r in estate.customer_rules()}
    answers = [a for a in classes["answer"]["items"] if a["id"] in rules and a["proposed_plan"] == "declare"]
    schema_all = json.loads((ROOT / "gen" / "jsonschema" / "contoso.schema.json").read_text())
    defs = schema_all["$defs"]
    schema = {"type": "object", "$defs": defs, "properties": {
        "approval_rules": {"type": "array", "items": {"$ref": "#/$defs/ContosoApprovalRule"}},
        "source_rules": {"type": "array", "items": {"type": "object", "properties": {
            "rule": {"type": "string"}, "approval_rule": {"type": ["string", "null"]},
            "note": {"type": "string"}}, "required": ["rule", "approval_rule", "note"]}}},
        "required": ["approval_rules", "source_rules"]}
    datasets = json.dumps([{k: d[k] for k in ("id", "classification", "domain", "owner")} for d in estate.datasets])
    users = {u["sys_id"]: {"user_name": u["user_name"], "role": slug(u.get("title"))} for u in estate.users.values()}
    prompt = f"""Translate Contoso's ServiceNow business rules into instances of Contoso's model (LinkML;
the JSON Schema you must answer in is generated from it). Each rule that decides who must approve a data access
request becomes one ContosoApprovalRule:
- approver_kind dataset_owner when the dataset's owner approves; role when anyone with approver_role approves.
- approver_role is a role id from: {json.dumps(roles(estate))}
- min_classification and domain narrow which datasets it applies to (classification order: public < internal <
  confidential < restricted). Datasets: {datasets}
- year_end_close_days, if the rule only applies in the days before the financial year end (31 March).
For rules that decide something other than approval (for example a required field), set approval_rule to null in
source_rules and say in the note which vocabulary term already expresses it.
Hard-coded sys_ids in scripts refer to these users: {json.dumps(users)}

Rules:
{json.dumps([{"rule": a["id"], "name": rules[a["id"]]["name"], "script": rules[a["id"]]["script"]} for a in answers], indent=1)}
"""
    if DECLARATIONS.exists() and not refresh:
        cached = json.loads(DECLARATIONS.read_text())
        if cached.get("prompt") == prompt:  # the same rules, datasets, roles and vocabulary: the same question
            return cached
    result = agent.ask(prompt, schema)
    out = {"rules": [a["id"] for a in answers], "prompt": prompt, "model": result["model"],
           "cost_usd": result["cost_usd"], "answer": result["answer"],
           "status": "proposed, awaiting confirmation by a person"}
    DECLARATIONS.write_text(json.dumps(out, indent=1))
    return out


YEAR_END = {"month": 3, "last_day": 31}  # Contoso's financial year ends 31 March (model/contoso.yaml)


def year_end_from_day(days: int) -> int:
    """The first day of March that a rule limited to the last `days` days of the financial year applies to.
    The one place the window is turned into a date test: the Python replay and the compiled rule both use it."""
    return YEAR_END["last_day"] - days + 1


def required_approvers(rules: list[dict], dataset: dict, opened: datetime) -> set[str]:
    """The model's decision: which approvers a request needs. 'owner' or a role id."""
    out = set()
    for r in rules:
        if r.get("domain") and r["domain"] != dataset["domain"]:
            continue
        if r.get("min_classification") and LEVEL[dataset["classification"]] < LEVEL[r["min_classification"]]:
            continue
        days = r.get("year_end_close_days")
        if days and not (opened.month == YEAR_END["month"] and opened.day >= year_end_from_day(days)):
            continue
        out.add("owner" if r["approver_kind"] == "dataset_owner" else r["approver_role"])
    return out


def history(estate: Estate, rec: dict) -> list[dict]:
    """What the old configuration actually did, request by request: who approved, in order."""
    datasets = {d["id"]: d for d in rec["datasets"]}
    users = {u["user_name"]: u for u in estate.users.values()}
    reqs = {r["id"]: r for r in rec["requests"]}
    by_req = defaultdict(list)
    for t in rec["tasks"]:
        if t["step"] == APPROVE:
            by_req[t["request"]].append(t)
    out = []
    for rid, r in reqs.items():
        d = datasets.get(r.get("dataset"))
        if not d:
            continue
        seen, rejected = set(), False
        for t in sorted(by_req.get(rid, []), key=lambda t: t["started_at"] or ""):
            seen.add("owner" if t["actor"] == d["owner"] else slug(users.get(t["actor"], {}).get("title")))
            rejected = rejected or t["outcome"]["status"] != "accepted"
        out.append({"request": rid, "dataset": d, "opened": datetime.fromisoformat(r["requested_at"].replace("Z", "+00:00")),
                    "approvers": seen, "rejected": rejected})
    return out


def replay(hist: list[dict], rules: list[dict]) -> list[dict]:
    """Compare each past request's approvals with what the rules decide. A rejection ends the chain, so then the
    past approvers need only be a subset."""
    diffs = []
    for h in hist:
        new = required_approvers(rules, h["dataset"], h["opened"])
        same = h["approvers"] <= new if h["rejected"] else h["approvers"] == new
        if not same:
            diffs.append({"request": h["request"], "opened": h["opened"].isoformat(), "dataset": h["dataset"]["id"],
                          "was": sorted(h["approvers"]), "model": sorted(new)})
    return diffs


def run(estate: Estate, rec: dict, classes: dict, usage: list[dict], refresh: bool = False) -> dict:
    steps = plan(estate, classes, usage)
    decl = declare(estate, classes, refresh=refresh)
    result = {**decide(steps, history(estate, rec), decl["answer"], replaced=set(slot_fields())),
              "declarations": decl["answer"],
              "datasets": rec["datasets"], "roles": roles(estate)}
    return confirm_plan(result, confirm.load())


def platform_payload(result: dict) -> dict:
    """Exactly what apply_plan installs: the compiled business rules and the generated catalogue item, as text.
    Built from the declared rules, the datasets, the roles and the vocabulary, so a change to any of them
    changes the payload, and the proposal that digests it."""
    from shopfloor.seed.apply import CATEGORY_ID
    compiled = compile_platform(compiled_rules(result), result["datasets"], result["roles"])
    return {"compiled": compiled, **catalogue_item(CATEGORY_ID)}


def plan_proposal(result: dict) -> dict:
    """The clean-up as one proposal: every proposed change, and the business rules and catalogue item that will
    be installed, as they will be installed. A person confirms it whole; any change to any of it gives it a new
    id."""
    changes = sorted((s["id"], s["kind"], s["plan"]) for s in result["plan"] if s["status"] == "proposed")
    compiled = compiled_rules(result)
    held = [s["name"] for s in result["plan"] if s["status"] == "held"]
    # What the replay cannot vouch for, named so the person reads it before confirming.
    unproved = [s["name"] for s in result["plan"] if s["status"] == "proposed" and s["kind"] == "business_rule"
                and s["replay"].get("diffs") is None]
    notes = [s["note"] for s in result["declarations"]["source_rules"] if s.get("approval_rule") and s.get("note")]
    return confirm.proposal(
        "repair", "cleanup", {"changes": changes, "compiled": compiled, "platform": platform_payload(result)},
        f"Clean-up: {len(changes)} changes. Approval rules proved against {result['replayed']:,} past requests; "
        f"catalogue items and fields decided by usage; {len(compiled)} approval rules compiled into the platform; "
        f"held for a person: {', '.join(held) or 'none'}. "
        f"The replay cannot test these, which carry no approval logic: {', '.join(unproved) or 'none'}. "
        f"Read the {len(notes)} translation notes: the replay compares roles, not people.",
        {"replayed": result["replayed"], "full_model_diffs": result["full_model_diffs"],
         "changes": [f"{p} {k} {i}" for i, k, p in changes], "compiled": [r["id"] for r in compiled],
         "not_testable_by_replay": unproved, "translation_notes": notes})


def confirm_plan(result: dict, confirmations: list[dict]) -> dict:
    """Apply the person's verdict on the proposal: approved, rejected, or still proposed (nothing is applied)."""
    prop = plan_proposal(result)
    v = confirm.verdict(confirmations, prop["id"])
    for s in result["plan"]:
        if s["status"] == "proposed" and v:
            s["status"] = "approved" if v == "approve" else "rejected"
    result["proposal"] = {**prop, "verdict": v}
    result["summary"] = dict(Counter(f"{s['plan']}:{s['status']}" for s in result["plan"]))
    return result


def compiled_rules(result: dict) -> list[dict]:
    """The approval rules the platform must enforce once the scripts go: every declared rule whose source script
    is retired by this plan. A held rule's script stays active, so it is not compiled twice."""
    by_rule = {s["rule"]: s for s in result["declarations"]["source_rules"]}
    rules_by_id = {r["id"]: r for r in result["declarations"]["approval_rules"]}
    going = {s["id"] for s in result["plan"] if s["kind"] == "business_rule" and s["status"] in ("proposed", "approved")}
    return [rules_by_id[s["approval_rule"]] for rid, s in sorted(by_rule.items())
            if rid in going and s.get("approval_rule") in rules_by_id]


def _replaced_by_compiler(step: dict, replaced: set[str]) -> bool:
    """A declared rule whose target is a request slot the compiled request-fields rule enforces (required, with
    the slot's pattern) is replaced by that rule, though the replay, which compares approvers, cannot see it."""
    term = step.get("target_term") or ""
    return step["plan"] == "declare" and "." in term and term.rsplit(".", 1)[1] in replaced


def decide(steps: list[dict], hist: list[dict], declarations: dict, replaced: set[str] | None = None) -> dict:
    """Prove each planned change against history. Pure: the plan, the history, the agent's translation and the
    request slots the compiler enforces in, a status for each change out."""
    replaced = replaced or set()
    by_rule = {s["rule"]: s for s in declarations["source_rules"]}
    rules_by_id = {r["id"]: r for r in declarations["approval_rules"]}

    def declared(exclude: set[str]) -> list[dict]:
        return [rules_by_id[s["approval_rule"]] for rid, s in by_rule.items()
                if s.get("approval_rule") in rules_by_id and rid not in exclude]

    # Replay the full translation first: does the model, as declared, reproduce history? If not, the
    # translation is wrong somewhere and no change can be proved against it: hold everything (fail closed).
    full = replay(hist, declared(set()))
    full_ids = {d["request"] for d in full}
    translated = {rid for rid, s in by_rule.items() if s.get("approval_rule") in rules_by_id}
    for s in steps:
        if s["plan"] == "keep":
            s["replay"], s["status"] = {"replayed": 0, "diffs": 0}, "kept"
            continue
        if full:
            s["replay"] = {"replayed": len(hist), "diffs": None}
            s["status"] = "held"
            s["held_because"] = (f"The declared model does not reproduce history ({len(full)} past decisions "
                                 "differ), so no change can be proved against it. Fix the translation first.")
            continue
        if s["kind"] != "business_rule":
            s["replay"] = {"replayed": 0, "diffs": 0, "note": "No decision logic; checked by usage only."}
            s["status"] = "proposed"
            continue
        if s["id"] in translated:
            if s["plan"] == "retire":
                d = [x for x in replay(hist, declared({s["id"]})) if x["request"] not in full_ids]
                s["replay"] = {"replayed": len(hist), "diffs": len(d), "examples": d[:5]}
            else:
                s["replay"] = {"replayed": len(hist), "diffs": 0,
                               "note": "Reproduced by the full model's replay."}
        else:
            s["replay"] = {"replayed": 0, "diffs": None,
                           "note": "No approval logic in the model, so the replay cannot test its effect."}
        if s["replay"]["diffs"]:
            s["status"] = "held"
            s["held_because"] = (f"Retiring it changes {s['replay']['diffs']} past decisions: the record shows it "
                                 "still acts, though not in the last 180 days.")
        elif s["replay"]["diffs"] is None and _replaced_by_compiler(s, replaced):
            s["replay"]["note"] += (" Replaced by the compiled request-fields rule, which enforces "
                                    f"{s['target_term'].rsplit('.', 1)[1]} from the model.")
            s["status"] = "proposed"
        elif s["replay"]["diffs"] is None and not (s["plan"] == "retire" and s.get("usage_180d", -1) == 0):
            # The replay cannot test it, so only the record can: a retire is proposed when usage shows the rule
            # never acts. A replacement or a reversion needs its replacement in place first, and a retire that
            # usage contradicts needs a person.
            s["status"] = "held"
            s["held_because"] = ("The replay cannot test it. " + (
                "Usage is unknown, so nothing proves the change safe." if s.get("usage_180d", -1) < 0 else
                f"It acted {s['usage_180d']} times in 180 days and nothing here replaces it."))
        else:
            s["status"] = "proposed"
    return {"plan": steps, "replayed": len(hist), "full_model_diffs": len(full),
            "full_model_examples": full[:10], "summary": dict(Counter(f"{s['plan']}:{s['status']}" for s in steps))}


APPLY_JS = """
var c = %s;
var undo = [];
for (var r = 0; r < c.compiled.length; r++) {
    var b = new GlideRecord('sys_script');
    if (!b.get(c.compiled[r].id)) { b.initialize(); b.setNewGuidValue(c.compiled[r].id); }
    for (var bf in c.compiled[r].f) b.setValue(bf, c.compiled[r].f[bf]);
    b.update() || b.insert();
    undo.push('compiled:' + c.compiled[r].id);
}
for (var i = 0; i < c.deactivate.length; i++) {
    var g = new GlideRecord(c.deactivate[i].table);
    if (g.get(c.deactivate[i].id) && g.getValue('active') == '1') {
        g.setValue('active', false); g.setWorkflow(false); g.update(); undo.push(c.deactivate[i].table + ':' + c.deactivate[i].id);
    }
}
for (var j = 0; j < c.hide_fields.length; j++) {
    var d = new GlideRecord('sys_dictionary');
    d.addQuery('name', 'sc_req_item'); d.addQuery('element', c.hide_fields[j]); d.query();
    while (d.next()) { d.setValue('active', false); d.update(); undo.push('hidden:' + c.hide_fields[j]); }
}
var it = new GlideRecord('sc_cat_item');
if (!it.get(c.item.id)) { it.initialize(); it.setNewGuidValue(c.item.id); }
for (var k in c.item.f) it.setValue(k, c.item.f[k]);
it.update() || it.insert();
for (var v = 0; v < c.variables.length; v++) {
    var q = new GlideRecord('item_option_new');
    if (!q.get(c.variables[v].id)) { q.initialize(); q.setNewGuidValue(c.variables[v].id); }
    for (var f in c.variables[v].f) q.setValue(f, c.variables[v].f[f]);
    q.update() || q.insert();
    for (var x = 0; x < c.variables[v].choices.length; x++) {
        var ch = new GlideRecord('question_choice');
        var cid = c.variables[v].choices[x].id;
        if (!ch.get(cid)) { ch.initialize(); ch.setNewGuidValue(cid); }
        ch.setValue('question', c.variables[v].id);
        ch.setValue('text', c.variables[v].choices[x].text);
        ch.setValue('value', c.variables[v].choices[x].value);
        ch.setValue('order', x * 100);
        ch.update() || ch.insert();
    }
}
report('undo ' + JSON.stringify(undo));
"""


def catalogue_item(category_id: str) -> dict:
    """The one catalogue item for the work, generated from the vocabulary: its variables are the request's
    slots, its choices the vocabulary's enumerations, its validation the vocabulary's patterns."""
    from shopfloor.seed.world import sys_id
    from shopfloor.vocab import view
    sv = view()
    item_id = sys_id("item", "wd-data-access")
    slots = {s.name: s for s in sv.class_induced_slots("ContosoAccessRequest")}
    datasets = json.loads((ROOT / "data" / "fixtures" / "datasets.json").read_text())["datasets"]
    variables = []
    for order, name in enumerate(["dataset", "privilege", "justification", "cost_centre", "duration_days"]):
        s = slots[name]
        f = {"cat_item": item_id, "name": name, "question_text": (s.description or name.replace("_", " ")).split(".")[0]
             if name not in ("dataset", "privilege") else name.capitalize(), "order": str(100 * (order + 1)),
             "mandatory": "true" if name in ("dataset", "privilege", "cost_centre") else "false", "active": "true"}
        choices = []
        if name == "dataset":
            f["type"] = "5"
            choices = [{"id": sys_id("choice", name, d["id"]), "text": d["name"], "value": d["id"]} for d in datasets]
        elif s.range in sv.all_enums():
            f["type"] = "5"
            choices = [{"id": sys_id("choice", name, v), "text": v, "value": v}
                       for v in sv.get_enum(s.range).permissible_values]
        elif s.range == "integer":
            f["type"] = "6"
        else:
            f["type"] = "2" if name == "justification" else "6"
        if s.pattern:
            f["example_text"] = s.pattern
        variables.append({"id": sys_id("var", item_id, name), "f": f, "choices": choices})
    return {"item": {"id": item_id, "f": {"name": "Request access to data", "short_description":
                                          "Request access to data (generated from the work vocabulary)",
                                          "active": "true", "category": category_id}},
            "variables": variables}


COMPILED_JS = """
(function executeRule(current, previous) {
    // Compiled from Contoso's model (model/contoso.yaml) by shopfloor. Do not edit: regenerate from the vocabulary.
    var m = %s;
    var d = m.datasets[current.getValue('u_dataset')];
    if (!d) return;
    var opened = new GlideDateTime();
    if (current.getValue('opened_at')) opened.setValueUTC(current.getValue('opened_at'), 'yyyy-MM-dd HH:mm:ss');
    var y = opened.getYearUTC(), month = opened.getMonthUTC(), day = opened.getDayOfMonthUTC();
    var who = {};
    for (var i = 0; i < m.rules.length; i++) {
        var r = m.rules[i];
        if (r.domain && r.domain != d.domain) continue;
        if (r.min_classification && m.level[d.classification] < m.level[r.min_classification]) continue;
        if (r.year_end_from_day && !(month == m.year_end.month && day >= r.year_end_from_day)) continue;
        who[r.approver_kind == 'dataset_owner' ? 'owner' : r.approver_role] = true;
    }
    for (var k in who) {
        var u = new GlideRecord('sys_user');
        if (k == 'owner') u.addQuery('user_name', d.owner); else u.addQuery('title', m.roles[k]);
        u.addActiveQuery();
        u.orderBy('user_name');
        u.query();
        while (u.next()) {
            var a = new GlideRecord('sysapproval_approver');
            a.initialize();
            a.sysapproval = current.sys_id;
            a.source_table = 'sc_req_item';
            a.approver = u.sys_id;
            a.state = 'requested';
            a.comments = 'Required by ' + k + ' (any one approves), from the model';
            a.insert();
        }
    }
})(current, previous);
"""

REQUIRED_JS = """
(function executeRule(current, previous) {
    // Compiled from Contoso's model (model/contoso.yaml) by shopfloor. Do not edit: regenerate from the vocabulary.
    // A request through the generated item carries the model's slots as catalogue variables; copy them onto the
    // request so the record, and every rule after this one, sees them.
    var item = %s, slots = %s;
    function val(name, field) {
        var f = current.getValue(field);
        if (f) return f;
        var v = current.variables[name];
        return v ? v + '' : '';
    }
    for (var name in slots) {
        var x = val(name, slots[name]);
        if (x && !current.getValue(slots[name])) current.setValue(slots[name], x);
    }
    var fromItem = current.getValue('cat_item') == item;
    if (!current.getValue('u_dataset')) {
        if (fromItem) {  // the generated item always names a dataset; without one, fail closed
            gs.addErrorMessage('dataset is required (Contoso model).');
            current.setAbortAction(true);
        }
        return;
    }
    var v = current.getValue('u_cost_centre') || '';
    if (!new RegExp(%s).test(v)) {
        gs.addErrorMessage('cost_centre is required and must match %s (Contoso model).');
        current.setAbortAction(true);
    }
})(current, previous);
"""

def slot_fields() -> dict[str, str]:
    """The request's slots that the generated item asks for, and the platform fields that carry them, from the
    ServiceNow mappings."""
    from shopfloor.mappings import crosswalk
    wanted = {"dataset", "privilege", "cost_centre", "justification"}
    return {m["slot"]: m["field"] for m in crosswalk("servicenow", "contoso-servicenow")
            if m["table"] == "sc_req_item" and m["slot"] in wanted}


def compile_platform(rules: list[dict], datasets: list[dict], roles: list[dict]) -> list[dict]:
    """Compile the declared approval rules, and the request's required, patterned cost centre, into business
    rules the platform runs. Generated from the model and never edited by hand; owners and role holders are
    looked up by name at run time, so no sys_id is hard-coded."""
    from shopfloor.seed.world import sys_id
    from shopfloor.vocab import view
    slot = next(s for s in view().class_induced_slots("ContosoAccessRequest") if s.name == "cost_centre")
    model = {"rules": [{**{k: r.get(k) for k in ("id", "approver_kind", "approver_role", "min_classification", "domain")},
                        "year_end_from_day": year_end_from_day(r["year_end_close_days"]) if r.get("year_end_close_days") else None}
                       for r in rules], "year_end": YEAR_END,
             "datasets": {d["id"]: {"domain": d["domain"], "classification": d["classification"], "owner": d["owner"]}
                          for d in datasets},
             "roles": {r["id"]: r["name"] for r in roles}, "level": LEVEL}
    base = {"collection": "sc_req_item", "active": "true", "advanced": "true", "action_insert": "true",
            "action_update": "false"}
    return [
        {"id": sys_id("compiled", "approval-rules"), "f": {**base, "name": "Approval rules (compiled from the model)",
                                                           "when": "after", "order": "50",
                                                           "script": COMPILED_JS % json.dumps(model, sort_keys=True)}},
        {"id": sys_id("compiled", "request-required"), "f": {**base, "name": "Request fields (compiled from the model)",
                                                             "when": "before", "order": "50",
                                                             "script": REQUIRED_JS % (
                                                                 json.dumps(sys_id("item", "wd-data-access")),
                                                                 json.dumps(slot_fields(), sort_keys=True), json.dumps(slot.pattern),
                                                                 slot.pattern)}}]


def apply_plan(sn, result: dict) -> dict:
    """Apply the approved changes: the payload the person confirmed, and nothing else. Held and kept
    customisations stay as they are."""
    approved = [s for s in result["plan"] if s["status"] == "approved"]
    if not approved:
        return {"applied": False, "reason": f"Nothing confirmed: proposal {result['proposal']['id']} has no "
                                             "approving confirmation in data/confirmations.yaml."}
    platform = platform_payload(result)
    compiled = platform["compiled"]
    deactivate = [{"table": "sys_script", "id": s["id"]} for s in approved if s["kind"] == "business_rule"]
    deactivate += [{"table": "sc_cat_item", "id": s["id"]} for s in approved if s["kind"] == "catalogue_item"]
    hide = [s["name"].split(".", 1)[1] for s in approved if s["kind"] == "custom_field" and s["plan"] == "retire"]
    payload = {**platform, "deactivate": deactivate, "hide_fields": hide}
    out = sn.run_script(APPLY_JS % json.dumps(payload))
    return {"applied": True, "compiled": [c["f"]["name"] for c in compiled], "deactivated": len(deactivate),
            "hidden_fields": hide, "drop_after": "a retention window the data owner sets; not done by the demo",
            "new_item": payload["item"]["id"], "variables": [v["f"]["name"] for v in payload["variables"]],
            "undo": out}
