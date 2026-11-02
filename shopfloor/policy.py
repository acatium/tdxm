"""Declared policy: access declared once, by role and classification, and compiled into the authority systems.

The policies are not invented. They are the policy candidates the diagnosis found in history: the cells where
every approver approved nearly every request. Three rules keep that honest:
- the evidence is every approval on a request (owner, security, controller), not the owner's alone;
- a policy covers a classification only if history at that classification and every one below it cleared the
  bar; and nothing above confidential is proposed without the data owner's own confirmation;
- the method is measured out of sample: derived from the first year, tested on the second.
"""

import json

import jsonschema
from oaaclient.templates import CustomApplication, OAAPermission

from shopfloor import confirm, store
from shopfloor.cleanup import LEVEL, slug
from shopfloor.diagnose import POLICY_BOUND, POLICY_MIN, wilson_lower
from shopfloor.vocab import ROOT

IMMUTA_SCHEMA = ROOT / "schemas" / "immuta" / "subscription-policy.schema.json"
ORDER = ["public", "internal", "confidential", "restricted"]
CAP = "confidential"  # above this, the data owner confirms in person


def rules_proved(cleanup_result: dict) -> list[dict]:
    """The approval rules policy may be derived under: the declared model, only if the replay reproduced
    history under it. Otherwise the translation is wrong somewhere and nothing is derived from it."""
    diffs = cleanup_result.get("full_model_diffs")
    if diffs:
        raise ValueError(f"The declared model does not reproduce history ({diffs} past decisions differ), "
                         "so no policy is derived under its rules. Fix the translation first.")
    return cleanup_result["declarations"]["approval_rules"]


def candidates(table: dict) -> dict:
    """Cells that clear the bar, keyed like the table."""
    return {k: c for k, c in table.items()
            if c["n"] >= POLICY_MIN and wilson_lower(c["approved"], c["n"]) >= POLICY_BOUND}


def derive(table: dict, approval_rules: list[dict] | None = None) -> list[dict]:
    """Candidate cells -> policies: one per role, domain and privilege. A policy reaches the highest
    classification where that classification and every one between it and the lowest with history cleared the
    bar; a classification with no history above the lowest stops it. No policy is declared over a domain that
    an approval rule with a time window touches: the grants Immuta and Veza hold have no window, so the policy
    would skip that rule all year."""
    passed = candidates(table)
    windowed = {r.get("domain") for r in approval_rules or [] if r.get("year_end_close_days")}
    groups: dict = {}
    for (title, domain, cls, privilege) in table:
        if domain in windowed or None in windowed:
            continue
        groups.setdefault((title, domain, privilege), set()).add(cls)
    policies = []
    for (title, domain, privilege), seen in sorted(groups.items(), key=lambda kv: tuple(map(str, kv[0]))):
        top, evidence = None, []
        for cls in ORDER:
            if cls not in seen:
                if top:
                    break  # no evidence here, so nothing above it is reached
                continue
            if (title, domain, cls, privilege) not in passed:
                break
            top = cls
            evidence.append(passed[(title, domain, cls, privilege)])
        if not top:
            continue
        n, ok = sum(c["n"] for c in evidence), sum(c["approved"] for c in evidence)
        role = slug(title)
        policies.append({"id": f"pol-{role}-{domain}-{privilege}", "role": role, "domain": domain,
                         "max_classification": top, "privilege": privilege, "effect": "allow",
                         "requires_approval": False,
                         "description": f"{role} may {privilege} {domain} data up to {top}: every approver approved "
                                        f"{ok} of {n} such requests (each classification's lower bound >= "
                                        f"{POLICY_BOUND})."})
    return policies


def covers(policy: dict, role: str | None, dataset: dict, privilege: str | None) -> bool:
    return (policy["role"] == role and policy["domain"] == dataset["domain"] and policy["privilege"] == privilege
            and LEVEL[dataset["classification"]] <= LEVEL[policy["max_classification"]])


def avoidable(rec: dict, policies: list[dict], titles: dict[str, str], since: str | None = None,
              until: str | None = None) -> dict:
    """Of the requests a person approved in [since, until), how many the policies would have made unnecessary.
    Rejected requests are not counted as avoidable: someone said no."""
    datasets = {d["id"]: d for d in rec["datasets"]}
    rejected = {t["request"] for t in rec["tasks"] if t["step"] == "st-approve" and t["outcome"]["status"] != "accepted"}
    total, covered, covered_rejected = 0, 0, 0
    for r in rec["requests"]:
        d = datasets.get(r.get("dataset"))
        if not d or (since and r["requested_at"] < since) or (until and r["requested_at"] >= until):
            continue
        hit = any(covers(p, slug(titles.get(r.get("on_behalf_of"))), d, r.get("privilege")) for p in policies)
        if r["id"] in rejected:
            covered_rejected += hit
            continue
        total += 1
        covered += hit
    return {"requests_approved": total, "covered": covered, "share": round(covered / total, 3) if total else 0.0,
            "covered_but_rejected": covered_rejected}


def proposals(policies: list[dict], datasets: list[dict], table: dict, measured: dict | None = None) -> list[dict]:
    """One proposal per policy. Above the cap, only the domain's data owner may confirm it. The summary says
    what the out-of-sample measurement showed, the requests a person rejected included: a policy replaces
    approvals that were a formality, and the person confirming it should see the refusals it would override."""
    out = []
    for p in policies:
        p_cells = {"/".join(map(str, k)): c["n"] for k, c in table.items()
                   if slug(k[0]) == p["role"] and k[1] == p["domain"] and k[3] == p["privilege"]}
        owners = sorted({d["owner"] for d in datasets if d["domain"] == p["domain"]})
        above = LEVEL[p["max_classification"]] > LEVEL[CAP]
        summary, evidence = p["description"], {"cells": p_cells}
        if measured:
            summary += (f" Measured on the year after: the proposed policies together cover {measured['covered']} of "
                        f"{measured['requests_approved']} approved requests, and {measured['covered_but_rejected']} "
                        f"that a person rejected.")
            evidence["measured_out_of_sample"] = measured
        out.append({**confirm.proposal("declared_policy", p["id"], p, summary, evidence,
                                       needs=f"the data owner ({', '.join(owners)})" if above else None),
                    "policy": p, "owners": owners if above else None})
    return out


def confirmed(props: list[dict], confirmations: list[dict]) -> tuple[list[dict], list[dict]]:
    """The policies a person confirmed, and every proposal with its verdict."""
    out, decided = [], []
    for pr in props:
        v = confirm.verdict(confirmations, pr["id"], set(pr["owners"]) if pr["owners"] else None)
        decided.append({k: pr[k] for k in ("id", "summary", "needs") if k in pr} | {"verdict": v})
        if v == "approve":
            out.append(pr["policy"])
    return out, decided


def compile_immuta(policies: list[dict]) -> list[dict]:
    """One subscription policy per policy and classification: Immuta's circumstances combine with one operator,
    so (domain AND classification) is expressed per classification."""
    out = []
    for p in policies:
        for cls in ORDER[: ORDER.index(p["max_classification"]) + 1]:
            out.append({
                "policyKey": f"{p['id']}-{cls}", "name": f"{p['id']} ({cls})", "type": "subscription",
                "actions": {"type": "entitlements", "accessGrant": "READ" if p["privilege"] == "read" else "WRITE",
                            "automaticSubscription": True, "allowDiscovery": True,
                            "description": p["description"],
                            "entitlements": {"operator": "any", "groups": [p["role"]]}},
                "circumstanceOperator": "all",
                "circumstances": [{"type": "tags", "tag": f"Contoso.Domain.{p['domain']}"},
                                  {"type": "tags", "tag": f"Contoso.Classification.{cls}"}],
                "staged": True})
    return out


def check_immuta(payloads: list[dict]) -> list[str]:
    schema = json.loads(IMMUTA_SCHEMA.read_text())
    v = jsonschema.Draft202012Validator(schema)
    return [f"{p.get('policyKey')}: {e.message}" for p in payloads for e in v.iter_errors(p)]


def compile_veza(policies: list[dict], datasets: list[dict]) -> dict:
    """The intended state as OAA roles, built with Veza's own SDK: one role per policy, holding the
    permission on every dataset the policy covers."""
    payloads = {}
    for platform in sorted({d["platform"] for d in datasets}):
        app = CustomApplication(f"contoso-{platform}-declared-policy", application_type="DataPlatform")
        app.add_custom_permission("read", [OAAPermission.DataRead])
        app.add_custom_permission("write", [OAAPermission.DataWrite])
        resources = {d["id"]: app.add_resource(d["id"], resource_type="dataset")
                     for d in datasets if d["platform"] == platform}
        for p in policies:
            covered = [resources[d["id"]] for d in datasets if d["id"] in resources
                       and d["domain"] == p["domain"] and LEVEL[d["classification"]] <= LEVEL[p["max_classification"]]]
            if covered:
                app.add_local_role(p["id"], permissions=[p["privilege"]])
                group = app.add_local_group(p["role"])
                group.add_role(p["id"], resources=covered)
        payloads[platform] = app.get_payload()
    return payloads


def validate_policies(policies: list[dict], roles: list[dict]) -> list[str]:
    return store.check({"policies": policies, "roles": roles})
