"""The mess that grew on Contoso's instance, planted from published anti-patterns. Each carries its true remedy
for the answer key and a citation for why it is an anti-pattern.

Sources for the anti-patterns:
- ServiceNow, "Business rules technical best practices" (avoid current.update() in business rules; use
  conditions; prefer async for integrations).
- ServiceNow, "Avoid hard-coding sys_ids" (scripting technical best practices).
- ServiceNow, "Service catalog: reduce catalog item sprawl" (catalogue governance guidance).
"""

from datetime import datetime, timezone

from shopfloor.seed.world import CHARGEBACK, World, sys_id, ts

BP_BR = "ServiceNow, Business rules technical best practices"
BP_SYSID = "ServiceNow, Scripting technical best practices: avoid hard-coded sys_ids"
BP_CAT = "ServiceNow, Service catalog governance: catalogue item sprawl"


def _d(y, m, d=1) -> str:
    return ts(datetime(y, m, d, 10, tzinfo=timezone.utc))


def plant(w: World) -> list[dict]:
    out = []
    recent_cut = "2026-05-03 00:00:00"  # 180 days before now
    recent_items = {r["cat_item"] for r in w.requests if r["opened_at"] >= recent_cut}
    used_items = {r["cat_item"] for r in w.requests}

    # Catalogue items: fourteen definitions of one kind of work.
    for k, it in enumerate(w.items):
        dead = it["sys_id"] not in recent_items
        out.append({
            "sys_id": it["sys_id"], "table": "sc_cat_item", "kind": "catalogue_item", "name": it["name"],
            "created_on": _d(2019 + k % 5, 1 + k % 12),
            "record": {"name": it["name"], "short_description": it["name"], "active": "true",
                       "category_name": "Data Access"},
            "truth": {"plan": "retire" if dead else "declare", "dead_by_usage": dead,
                      "target": "work:WorkDefinition wd-data-access", "cite": BP_CAT,
                      "ever_used": it["sys_id"] in used_items}})

    # Custom fields on requested items.
    fields = [
        ("u_cost_centre", "Cost centre", "declare", False, "org:ContosoAccessRequest.cost_centre"),
        ("u_dataset", "Dataset", "declare", False, "access:AccessRequest.dataset"),
        ("u_privilege", "Privilege", "declare", False, "access:AccessRequest.privilege"),
        ("u_approval_level", "Approval level", "retire", True, None),
        ("u_legacy_ticket_ref", "Legacy ticket reference", "retire", True, None),
        ("u_chargeback_amount", "Chargeback amount", "keep", False, None),
    ]
    for k, (element, label, plan, dead, target) in enumerate(fields):
        out.append({
            "sys_id": sys_id("field", element), "table": "sys_dictionary", "kind": "custom_field",
            "name": f"sc_req_item.{element}", "created_on": _d(2020 + k % 3, 3 + k),
            "record": {"name": "sc_req_item", "element": element, "internal_type": "string", "max_length": 80,
                       "column_label": label},
            "truth": {"plan": plan, "dead_by_usage": dead, "target": target, "cite": BP_BR}})

    owners = {d["domain"]: next(u for u in w.users if u["user_name"] == d["owner"])["sys_id"] for d in w.datasets}
    domains = {d["id"]: d["domain"] for d in w.datasets}
    classes = {d["id"]: d["classification"] for d in w.datasets}
    security = [u["sys_id"] for u in w.users if u["role"] == "security"]
    controllers = [u["sys_id"] for u in w.users if u["role"] == "controller"]

    def js(o) -> str:
        import json
        return json.dumps(o, sort_keys=True)

    rules = [
        ("Require cost centre on data access", "before", "insert", "declare", False,
         "org:ContosoAccessRequest.cost_centre (pattern ^CC-[0-9]{4}$)", False, f"""
(function executeRule(current, previous) {{
    if (current.cat_item.category.getDisplayValue() != 'Data Access') return;
    var cc = current.getValue('u_cost_centre') || '';
    if (!/^CC-[0-9]{{4}}$/.test(cc)) {{
        gs.addErrorMessage('A cost centre (CC-1234) is required for data access requests.');
        current.setAbortAction(true);
    }}
}})(current, previous);"""),
        ("Data owner approval", "after", "insert", "declare", False,
         "access:ApprovalRule (approver_kind dataset_owner)", False, f"""
(function executeRule(current, previous) {{
    // Owners by domain. Updated by hand when owners change.
    var owners = {js(owners)};
    var domains = {js(domains)};
    var approver = owners[domains[current.getValue('u_dataset')]];
    if (!approver) return;
    var a = new GlideRecord('sysapproval_approver');
    a.initialize();
    a.sysapproval = current.sys_id;
    a.approver = approver;
    a.state = 'requested';
    a.insert();
}})(current, previous);"""),
        ("Security approval for restricted data", "after", "insert", "declare", False,
         "access:ApprovalRule (approver_kind role, approver_role security, min_classification restricted)", False, f"""
(function executeRule(current, previous) {{
    var restricted = {js(sorted(k for k, v in classes.items() if v == 'restricted'))};
    if (restricted.indexOf(current.getValue('u_dataset')) < 0) return;
    var a = new GlideRecord('sysapproval_approver');
    a.initialize();
    a.sysapproval = current.sys_id;
    a.approver = '{security[0]}';  // security team lead
    a.state = 'requested';
    a.insert();
}})(current, previous);"""),
        ("Finance year-end approval", "after", "insert", "declare", True,
         "org:ContosoApprovalRule (approver_role controller, domain finance, year_end_close_days 10)", True, f"""
(function executeRule(current, previous) {{
    // FY close: finance data needs the controller as well, from 22 March to 31 March.
    var finance = {js(sorted(k for k, v in domains.items() if v == 'finance'))};
    if (finance.indexOf(current.getValue('u_dataset')) < 0) return;
    var now = new GlideDateTime();
    var month = now.getMonthUTC(), day = now.getDayOfMonthUTC();
    if (!(month == 3 && day >= 22)) return;
    var a = new GlideRecord('sysapproval_approver');
    a.initialize();
    a.sysapproval = current.sys_id;
    a.approver = '{controllers[0]}';
    a.state = 'requested';
    a.insert();
}})(current, previous);"""),
        ("Close request item when tasks complete", "after", "update", "revert_to_base", False,
         "Platform base behaviour (request item stage and state from its catalogue tasks)", False, """
(function executeRule(current, previous) {
    var t = new GlideRecord('sc_task');
    t.addQuery('request_item', current.sys_id);
    t.addQuery('active', true);
    t.query();
    if (!t.hasNext() && current.state != 3) {
        current.state = 3;
        current.update();  // re-enters business rules
    }
})(current, previous);"""),
        ("Sync access request to Snowflake (legacy)", "async", "insert", "retire", True,
         "Its intent is covered by the compiler's Immuta and Veza adapters (step 5)", False, """
(function executeRule(current, previous) {
    if (gs.getProperty('contoso.snowflake.sync.enabled', 'false') != 'true') return;
    var r = new sn_ws.RESTMessageV2('Contoso Snowflake', 'grant');
    r.setStringParameterNoEscape('user', current.requested_for.user_name);
    r.setStringParameterNoEscape('object', current.getValue('u_dataset'));
    r.setStringParameterNoEscape('privilege', current.getValue('u_privilege'));
    var resp = r.execute();
    current.work_notes = 'Snowflake sync: ' + resp.getStatusCode();
    current.update();
})(current, previous);"""),
        ("Escalate VIP data requests", "after", "insert", "retire", True, None, False, """
(function executeRule(current, previous) {
    if (current.getValue('u_approval_level') != 'VIP') return;
    gs.eventQueue('contoso.vip.request', current, current.requested_for, '');
})(current, previous);"""),
        ("Copy dataset into description (2022)", "before", "insert", "retire", True, None, False, """
(function executeRule(current, previous) {
    if (current.getValue('u_legacy_ticket_ref') == '') return;
    current.description = 'Dataset: ' + current.getValue('u_dataset') + '\\n' + current.description;
})(current, previous);"""),
        ("Allocate data access chargeback", "before", "insert", "keep", False, None, False, f"""
(function executeRule(current, previous) {{
    // Finance charges each cost centre per dataset per month. Rates agreed with Finance, FY2024.
    var rates = {js(CHARGEBACK)};
    var r = rates[current.getValue('u_dataset')];
    if (r) current.setValue('u_chargeback_amount', r * (current.getValue('u_privilege') == 'read' ? 1 : 3));
}})(current, previous);"""),
    ]
    for k, (name, when, op, plan, dead, target, trap, script) in enumerate(rules):
        out.append({
            "sys_id": sys_id("rule", name), "table": "sys_script", "kind": "business_rule", "name": name,
            "created_on": _d(2019 + k % 6, 2 + k),
            "record": {"name": name, "collection": "sc_req_item", "when": when, "active": "true",
                       "action_insert": "true" if op == "insert" else "false",
                       "action_update": "true" if op == "update" else "false",
                       "advanced": "true", "order": 100 + k * 10, "script": script.strip()},
            "truth": {"plan": plan, "dead_by_usage": dead, "target": target, "trap": trap,
                      "cite": BP_SYSID if "owners" in script or "approver = '" in script else BP_BR}})
    return out
