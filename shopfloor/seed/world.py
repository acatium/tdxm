"""Contoso Capital's data-access world: two years of history under the old configuration, the mess that
grew on the platform, and the answer key.

Deterministic: a fixed seed and a fixed "now". The old configuration's behaviour is written here once, as
plain rules, so the history is what those rules would have produced. The demo later has to rediscover them
from the platform and the record alone; it never reads this module.
"""

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from shopfloor.diagnose import POLICY_MIN  # the answer key names a candidate at the same bar the diagnosis uses

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)
START = datetime(2024, 11, 1, tzinfo=timezone.utc)
SEED = 20261030
YEAR_END_CLOSE_DAYS = 10  # the trap: controller approval for finance data in the last 10 days to 31 March


def sys_id(*parts) -> str:
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()


def _uuid(*parts) -> str:
    h = sys_id(*parts)
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def ts(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# --- Roles, people, agents, datasets ---

ROLES = {
    "analyst": ("Credit analyst", "Credit"),
    "quant": ("Quantitative researcher", "Markets"),
    "engineer": ("Data engineer", "Data Platform"),
    "controller": ("Finance controller", "Finance"),
    "owner": ("Data owner", "Data Office"),
    "security": ("Security analyst", "IT Security"),
    "iam": ("Access administrator", "IT"),
    "contractor": ("Contract analyst", "Credit"),
}
HEADCOUNT = {"analyst": 14, "quant": 9, "engineer": 7, "controller": 4, "owner": 5, "security": 3, "iam": 3,
             "contractor": 5}
FIRST = ["Amaya", "Ben", "Chloe", "Dev", "Elena", "Farid", "Grace", "Hiro", "Ines", "Jonas", "Kemi", "Liam",
         "Mira", "Noah", "Olu", "Priya", "Quinn", "Rosa", "Sam", "Tara", "Uma", "Victor", "Wen", "Xavi", "Yara",
         "Zane", "Ada", "Bo", "Cyrus", "Dina", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jade", "Kai", "Lena", "Max",
         "Nia", "Omar", "Pia", "Raj", "Sia", "Tom", "Una", "Vik", "Will", "Xia", "Yusuf"]
LAST = ["Okafor", "Lindqvist", "Moreau", "Patel", "Novak", "Haddad", "Kim", "Tanaka", "Silva", "Berg",
        "Adeyemi", "Walsh", "Rossi", "Cohen", "Mensah", "Iyer", "Doyle", "Garcia", "Reid", "Shah"]

# (id, name, platform, classification, domain)
DATASETS = [
    ("loan_book", "Loan book", "snowflake", "confidential", "credit"),
    ("credit_risk_mart", "Credit risk mart", "snowflake", "confidential", "credit"),
    ("counterparty_exposure", "Counterparty exposure", "snowflake", "restricted", "credit"),
    ("market_data_eod", "Market data (end of day)", "databricks", "internal", "markets"),
    ("trade_blotter", "Trade blotter", "databricks", "confidential", "markets"),
    ("research_notes", "Research notes", "databricks", "internal", "markets"),
    ("fx_rates", "FX rates", "snowflake", "public", "markets"),
    ("esg_scores", "ESG scores", "snowflake", "public", "markets"),
    ("gl_actuals", "General ledger actuals", "snowflake", "restricted", "finance"),
    ("budget_forecast", "Budget forecast", "snowflake", "confidential", "finance"),
    ("client_master", "Client master", "snowflake", "restricted", "operations"),
    ("payroll", "Payroll", "snowflake", "restricted", "hr"),
]
# Monthly chargeback per dataset, by the cost centre that asks. Contoso's own practice: no vocabulary term yet.
CHARGEBACK = {"loan_book": 40, "credit_risk_mart": 60, "counterparty_exposure": 80, "market_data_eod": 120,
              "trade_blotter": 90, "research_notes": 20, "fx_rates": 10, "esg_scores": 15, "gl_actuals": 50,
              "budget_forecast": 30, "client_master": 70, "payroll": 25}

LEVEL = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}

# Who usually asks for what: role -> (home domains, ceiling classification for declared policy)
AFFINITY = {
    "analyst": (["credit"], "confidential"),
    "contractor": (["credit"], "internal"),
    "quant": (["markets"], "confidential"),
    "engineer": (["credit", "markets", "finance", "operations"], "internal"),
    "controller": (["finance"], "restricted"),
}

# The access policies Contoso actually applies, though nobody wrote them down in one place. These are what the
# model should end up declaring; declared policy means no request is needed.
POLICIES = [
    {"id": "pol-analyst-credit", "role": "analyst", "domain": "credit", "max": "confidential", "privilege": "read"},
    {"id": "pol-contractor-credit", "role": "contractor", "domain": "credit", "max": "internal", "privilege": "read"},
    {"id": "pol-quant-markets", "role": "quant", "domain": "markets", "max": "confidential", "privilege": "read"},
    {"id": "pol-engineer-internal", "role": "engineer", "domain": "*", "max": "internal", "privilege": "read"},
    {"id": "pol-controller-finance", "role": "controller", "domain": "finance", "max": "restricted", "privilege": "read"},
    {"id": "pol-public", "role": "*", "domain": "*", "max": "public", "privilege": "read"},
]


def covered_by_policy(role: str, ds: tuple, privilege: str) -> str | None:
    for p in POLICIES:
        if p["privilege"] != privilege:
            continue
        if p["role"] not in ("*", role):
            continue
        if p["domain"] not in ("*", ds[4]):
            continue
        if LEVEL[ds[3]] <= LEVEL[p["max"]]:
            return p["id"]
    return None


# --- Catalogue items: fourteen ways to ask for the same thing ---

# (key, name, used_from, used_to, weight). None = never used in the two-year window.
CATALOGUE = [
    ("snowflake_access", "Request access to Snowflake", START, datetime(2025, 9, 1, tzinfo=timezone.utc), 5),
    ("snowflake_access_req", "Snowflake access request", START, datetime(2025, 3, 1, tzinfo=timezone.utc), 2),
    ("data_access_loan_book", "Data access - Loan book", START, NOW, 2),
    ("finance_read", "Request read access (Finance data)", START, NOW, 2),
    ("databricks_workspace", "Databricks workspace access", START, NOW, 3),
    ("credit_risk_mart", "Access to Credit Risk data mart", START, datetime(2025, 6, 1, tzinfo=timezone.utc), 1),
    ("tableau_data", "Tableau / data access", START, datetime(2025, 1, 15, tzinfo=timezone.utc), 1),
    ("new_data_access_2023", "New data access request (2023)", None, None, 0),
    ("do_not_use", "Data access request - DO NOT USE", None, None, 0),
    ("restricted_data", "Request access to restricted data", START, NOW, 2),
    ("analytics_platform", "Analytics platform access", datetime(2025, 9, 1, tzinfo=timezone.utc), NOW, 6),
    ("market_data", "Access request: market data", START, NOW, 2),
    ("data_share", "Data share request", None, None, 0),
    ("powerbi_dataset", "Request Power BI dataset access", START, datetime(2025, 4, 1, tzinfo=timezone.utc), 1),
]


@dataclass
class World:
    users: list[dict] = field(default_factory=list)
    agents: list[dict] = field(default_factory=list)
    datasets: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)
    approvals: list[dict] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)
    grants: list[dict] = field(default_factory=list)
    # Every grant the authority system ever recorded, revoked or not: the history behind the standing grants.
    grant_events: list[dict] = field(default_factory=list)
    spans: list[dict] = field(default_factory=list)
    armis_assets: list[dict] = field(default_factory=list)
    moveworks_intake: list[dict] = field(default_factory=list)
    customisations: list[dict] = field(default_factory=list)
    truth: dict = field(default_factory=dict)


def _in_year_end_close(d: datetime) -> bool:
    end = datetime(d.year, 3, 31, 23, 59, tzinfo=timezone.utc)
    return end - timedelta(days=YEAR_END_CLOSE_DAYS) <= d <= end


def build() -> World:
    rnd = random.Random(SEED)
    w = World()

    # People
    names = [(f, l) for l in LAST for f in FIRST]
    rnd.shuffle(names)
    i = 0
    people_by_role: dict[str, list[dict]] = {}
    for role, n in HEADCOUNT.items():
        for _ in range(n):
            first, last = names[i]
            i += 1
            u = {"sys_id": sys_id("user", first, last), "user_name": f"{first.lower()}.{last.lower()}",
                 "first_name": first, "last_name": last, "email": f"{first.lower()}.{last.lower()}@contoso.example",
                 "title": ROLES[role][0], "department_name": ROLES[role][1], "role": role, "kind": "person"}
            w.users.append(u)
            people_by_role.setdefault(role, []).append(u)

    # Agents and service accounts. Two are ServiceNow users; the notebook agent is known to nobody but Armis.
    access_agent = {"sys_id": sys_id("user", "svc.access.agent"), "user_name": "svc.access.agent",
                    "first_name": "Access", "last_name": "Agent", "email": "access-agent@contoso.example",
                    "title": "Access fulfilment agent", "department_name": "IT", "role": "agent", "kind": "agent",
                    "registered": True, "host": "agent-runtime-01", "owner": people_by_role["iam"][0]["user_name"]}
    pipeline = {"sys_id": sys_id("user", "svc_data_pipeline"), "user_name": "svc_data_pipeline",
                "first_name": "Data", "last_name": "Pipeline", "email": "data-pipeline@contoso.example",
                "title": "Shared service account", "department_name": "Data Platform", "role": "service",
                "kind": "service_account", "registered": True, "host": "etl-01",
                "owner": people_by_role["engineer"][0]["user_name"]}
    notebook = {"user_name": "nb-research-agent", "kind": "agent", "registered": False, "host": "ws-quant-07",
                "owner": people_by_role["quant"][2]["user_name"]}
    w.users += [access_agent, pipeline]
    w.agents = [access_agent, pipeline, notebook]

    # Datasets and their owners
    owners = people_by_role["owner"]
    domain_owner = {d: owners[k % len(owners)] for k, d in enumerate(sorted({x[4] for x in DATASETS}))}
    for (did, name, platform, cls, domain) in DATASETS:
        w.datasets.append({"id": did, "name": name, "platform": platform, "classification": cls, "domain": domain,
                           "owner": domain_owner[domain]["user_name"]})
    ds_by_id = {d[0]: d for d in DATASETS}

    for key, name, frm, to, weight in CATALOGUE:
        w.items.append({"sys_id": sys_id("item", key), "key": key, "name": name, "used_from": frm, "used_to": to,
                        "weight": weight})

    # --- Two years of requests under the old configuration ---
    requesters = [u for r in AFFINITY for u in people_by_role[r]]
    controllers = people_by_role["controller"]
    security = people_by_role["security"]
    iam = people_by_role["iam"]
    n = 0
    day = START
    while day < NOW:
        for _ in range(rnd.choices([2, 4, 5, 6, 8], [1, 2, 4, 2, 1])[0] if day.weekday() < 5 else rnd.choice([0, 0, 1])):
            u = rnd.choice(requesters)
            home, _ = AFFINITY[u["role"]]
            pool = [d for d in DATASETS if d[4] in home] if rnd.random() < 0.8 else DATASETS
            ds = rnd.choice(pool)
            privilege = rnd.choices(["read", "write", "admin"], [85, 12, 3])[0]
            opened = day + timedelta(hours=rnd.uniform(8, 18))
            if opened >= NOW:
                continue
            live_items = [it for it in w.items if it["used_from"] and it["used_from"] <= opened < it["used_to"]]
            item = rnd.choices(live_items, [it["weight"] for it in live_items])[0]
            n += 1
            number = f"RITM1{n:06d}"
            rid = sys_id("ritm", n)
            via_chat = opened >= datetime(2025, 9, 1, tzinfo=timezone.utc) and rnd.random() < 0.6
            policy = covered_by_policy(u["role"], ds, privilege)
            req = {"sys_id": rid, "number": number, "cat_item": item["sys_id"], "requested_for": u["sys_id"],
                   "opened_by": u["sys_id"], "opened_at": ts(opened), "u_dataset": ds[0], "u_privilege": privilege,
                   "u_cost_centre": f"CC-{4100 + (int(sys_id(u['user_name'])[:4], 16) % 7) * 10}",
                   "u_chargeback_amount": str(CHARGEBACK[ds[0]] * (1 if privilege == "read" else 3)),
                   "short_description": f"Access to {ds[1]} ({privilege})",
                   "description": rnd.choice(["Needed for quarterly review", "New project", "Model validation",
                                              "Month-end reporting", "Audit request", "Covering for a colleague"]),
                   "channel": "moveworks" if via_chat else "portal", "policy": policy,
                   "requester_role": u["role"]}
            # Approvals: the data owner always; security for restricted; the controller in the year-end close
            # for finance data (the rule that looks dead).
            t = opened + timedelta(minutes=rnd.uniform(20, 600))
            approvals = [("owner", domain_owner[ds[4]])]
            if ds[3] == "restricted":
                approvals.append(("security", rnd.choice(security)))
            if ds[4] == "finance" and _in_year_end_close(opened):
                approvals.append(("controller", rnd.choice(controllers)))
            rejected = False
            for k, (why, approver) in enumerate(approvals):
                p_reject = 0.005 if policy else (0.12 if privilege != "read" else 0.05)
                state = "rejected" if rnd.random() < p_reject else "approved"
                t = t + timedelta(minutes=rnd.uniform(10, 900))
                w.approvals.append({"sys_id": sys_id("appr", n, k), "sysapproval": rid, "approver": approver["sys_id"],
                                    "state": state, "why": why, "sys_created_on": ts(opened),
                                    "sys_updated_on": ts(min(t, NOW - timedelta(minutes=1)))})
                if state == "rejected":
                    rejected = True
                    break
            if rejected:
                req.update(state=4, closed_at=ts(min(t, NOW - timedelta(minutes=1))), reassignment_count=0,
                           outcome="rejected")
                w.requests.append(req)
                continue
            # Provisioning: people at first, the access agent increasingly from mid-2025
            share = 0.0 if opened < datetime(2025, 6, 1, tzinfo=timezone.utc) else min(0.75, 0.15 + (opened - datetime(2025, 6, 1, tzinfo=timezone.utc)).days / 400)
            by_agent = rnd.random() < share
            fulfiller = access_agent if by_agent else rnd.choice(iam)
            start = t + timedelta(minutes=rnd.uniform(5, 240 if not by_agent else 10))
            end = start + timedelta(minutes=rnd.uniform(1, 5) if by_agent else rnd.uniform(30, 2880))
            # Planted rates. The agent's record is planted to clear the autonomy bar (results/README.md says so);
            # the demo shows the mechanism that reads the record, not that agents do the work better.
            reassigned = rnd.random() < (0.01 if by_agent else 0.09)
            if reassigned:
                end += timedelta(hours=rnd.uniform(4, 72))
            if end >= NOW:
                end = NOW - timedelta(minutes=1)
            tid = sys_id("task", n)
            w.tasks.append({"sys_id": tid, "number": f"SCTASK1{n:06d}", "request_item": rid,
                            "assigned_to": fulfiller["sys_id"], "opened_at": ts(start), "closed_at": ts(end),
                            "short_description": f"Provision {privilege} on {ds[1]}", "state": 3,
                            "reassignment_count": 1 if reassigned else 0, "by_agent": by_agent})
            reversed_ = rnd.random() < (0.05 if privilege != "read" else 0.02) * (0.4 if by_agent else 1.0)
            req.update(state=3, closed_at=ts(end), reassignment_count=1 if reassigned else 0,
                       outcome="reversed" if reversed_ else ("reassigned" if reassigned else "accepted"))
            w.requests.append(req)
            if reversed_:
                # The grant was made, then revoked within its window: the authority system's history shows both.
                w.grant_events.append({"actor": u["user_name"], "dataset": ds[0], "privilege": privilege,
                                       "granted_at": ts(end), "revoked_at": ts(end + timedelta(days=7)),
                                       "last_used_at": None})
            else:
                u_ = rnd.random()
                if u_ < 0.15:
                    last_used = None  # granted and never used
                elif u_ < 0.30:
                    last_used = ts(min(NOW - timedelta(days=91), end + timedelta(days=rnd.uniform(1, 60))))
                else:
                    last_used = ts(max(end, NOW - timedelta(days=rnd.uniform(0, 60))))
                w.grants.append({"id": f"g-{n}", "actor": u["user_name"], "dataset": ds[0], "privilege": privilege,
                                 "granted_at": ts(end), "request": number, "last_used_at": last_used})
                w.grant_events.append({"actor": u["user_name"], "dataset": ds[0], "privilege": privilege,
                                       "granted_at": ts(end), "revoked_at": None, "last_used_at": last_used})
            if via_chat:
                w.moveworks_intake.append({
                    "meta_info": {"user": {"email_addr": u["email"]}, "action_instance_id": _uuid("mw", n)},
                    "data": {"dataset": ds[0], "privilege": privilege, "justification": req["description"],
                             "cost_centre": req["u_cost_centre"]},
                    "created": ts(opened), "ticket": number})
        day += timedelta(days=1)

    # --- Drift and standing privilege nobody asked for ---
    for k, did in enumerate(["counterparty_exposure", "gl_actuals", "client_master", "trade_blotter", "loan_book",
                             "payroll", "budget_forecast", "credit_risk_mart"]):
        w.grants.append({"id": f"g-svc-{k}", "actor": "svc_data_pipeline", "dataset": did,
                         "privilege": "admin" if k % 2 == 0 else "write", "granted_at": ts(START - timedelta(days=200 + k)),
                         "request": None, "last_used_at": ts(NOW - timedelta(days=rnd.uniform(1, 20))) if k < 3 else None})
    for k in range(6):  # grants made outside any request, e.g. by hand in the console
        u = rnd.choice(requesters)
        ds = rnd.choice(DATASETS)
        w.grants.append({"id": f"g-drift-{k}", "actor": u["user_name"], "dataset": ds[0], "privilege": "read",
                         "granted_at": ts(START + timedelta(days=rnd.uniform(0, 700))), "request": None,
                         "last_used_at": None})
    w.grants.append({"id": "g-nb", "actor": notebook["owner"], "dataset": "client_master", "privilege": "read",
                     "granted_at": ts(NOW - timedelta(days=60)), "request": None,
                     "last_used_at": ts(NOW - timedelta(days=1))})

    # --- Agent telemetry, last 30 days ---
    recent = [r for r in w.requests if r.get("closed_at") and r["closed_at"] >= ts(NOW - timedelta(days=30))]
    task_by_req = {t["request_item"]: t for t in w.tasks}
    for r in recent:
        t = task_by_req.get(r["sys_id"])
        if t and t["by_agent"]:
            w.spans.append({"agent": "svc.access.agent", "operation": "grant", "target_system": r["u_dataset"],
                            "at": t["closed_at"], "request": r["number"], "host": "agent-runtime-01"})
    for k in range(40):
        did = rnd.choice(["counterparty_exposure", "gl_actuals", "client_master"])
        w.spans.append({"agent": "svc_data_pipeline", "operation": rnd.choice(["query", "query", "grant"]),
                        "target_system": did, "at": ts(NOW - timedelta(days=rnd.uniform(0, 30))), "request": None,
                        "host": "etl-01"})
    for k in range(25):
        w.spans.append({"agent": "nb-research-agent", "operation": "query", "target_system": "client_master",
                        "at": ts(NOW - timedelta(days=rnd.uniform(0, 14))), "request": None, "host": "ws-quant-07"})

    # --- Armis: the hosts the agents run on ---
    for k, (host, display, tags) in enumerate([
            ("agent-runtime-01", "agent-runtime-01", ["agent-registry:svc.access.agent", "Server"]),
            ("etl-01", "etl-01", ["agent-registry:svc_data_pipeline", "Server"]),
            ("ws-quant-07", "WS-QUANT-07", ["Workstation", "Python", "Jupyter"])]):
        w.armis_assets.append({"asset_id": 1000 + k, "fields": {
            "device_id": 1000 + k, "display": display, "brand": "Dell", "model": "PowerEdge R650" if k < 2 else "Precision 5680",
            "tags": tags, "last_seen": (NOW - timedelta(hours=k + 1)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "ipv4_addresses": [f"10.20.{k}.{10 + k}"], "mac_addresses": [f"00:1a:2b:3c:4d:{10 + k:02x}"]}})

    # One standing grant per person, dataset and privilege, as the authority system holds it. A repeat request
    # for access already held refreshes it.
    merged: dict[tuple, dict] = {}
    for g in w.grants:
        k = (g["actor"], g["dataset"], g["privilege"])
        if k in merged:
            old = merged[k]
            old["last_used_at"] = max(filter(None, [old["last_used_at"], g["last_used_at"]]), default=None)
            old["request"] = old["request"] or g["request"]
        else:
            merged[k] = g
    w.grants = list(merged.values())

    from shopfloor.seed.customisations import plant
    w.customisations = plant(w)
    w.truth = truth(w)
    return w


def truth(w: World) -> dict:
    """The answer key. The diagnosis is scored against this; nothing in the demo reads it except the scorer."""
    gaps = []
    for it in w.items:
        gaps.append({"kind": "duplicate_definition", "subject": it["sys_id"], "name": it["name"]})
    for c in w.customisations:
        if c["truth"]["dead_by_usage"]:
            gaps.append({"kind": "dead_customisation", "subject": c["sys_id"], "name": c["name"]})
        if c["truth"]["plan"] == "keep":
            gaps.append({"kind": "vocabulary", "subject": c["sys_id"], "name": c["name"]})
    for g in w.grants:
        key = f'{g["actor"]}:{g["dataset"]}:{g["privilege"]}'
        if g["request"] is None:
            gaps.append({"kind": "drift", "subject": key})
        if g["last_used_at"] is None or g["last_used_at"] < ts(NOW - timedelta(days=90)):
            gaps.append({"kind": "idle_privilege", "subject": key})
    gaps.append({"kind": "orphan_action", "subject": "svc_data_pipeline"})
    gaps.append({"kind": "orphan_action", "subject": "nb-research-agent"})
    gaps.append({"kind": "unregistered_actor", "subject": "nb-research-agent"})
    # Promotion candidates: owner approvals in the cells an unwritten policy covers, with enough volume to tell.
    ds_by_id = {d[0]: d for d in DATASETS}
    owner_appr = {a["sysapproval"] for a in w.approvals if a["why"] == "owner"}
    cells: dict[tuple, int] = {}
    for r in w.requests:
        if r["sys_id"] in owner_appr and r["policy"]:
            d = ds_by_id[r["u_dataset"]]
            k = (r["requester_role"], d[4], d[3], r["u_privilege"])
            cells[k] = cells.get(k, 0) + 1
    for k, n in sorted(cells.items()):
        if n >= POLICY_MIN:
            gaps.append({"kind": "policy_candidate", "subject": "approve:" + ":".join(k), "volume": n})
    plans = {c["sys_id"]: {"name": c["name"], "plan": c["truth"]["plan"], "trap": c["truth"].get("trap", False)}
             for c in w.customisations}
    covered = sum(1 for r in w.requests if r["policy"])
    return {"now": ts(NOW), "gaps": gaps, "plans": plans,
            "requests": len(w.requests), "requests_covered_by_policy": covered,
            "policies": POLICIES, "year_end_close_days": YEAR_END_CLOSE_DAYS}
