"""Score the diagnosis against the answer key. The only module besides the seeder that reads the truth."""

from collections import defaultdict

import yaml

from shopfloor.seed.world import ROLES
from shopfloor.vocab import ROOT

TRUTH = ROOT / "data" / "truth.yaml"


def _norm(kind: str, subject: str) -> str:
    if kind in ("drift", "idle_privilege") and subject.count(":") == 3:
        return subject.split(":", 1)[1]  # platform:actor:dataset:privilege -> actor:dataset:privilege
    if kind == "policy_candidate":
        parts = subject.split(":")
        titles = {title: key for key, (title, _) in ROLES.items()}
        parts[1] = titles.get(parts[1], parts[1])
        return ":".join(parts)
    return subject


def score(gaps: list[dict], truth: dict | None = None) -> dict:
    truth = truth or yaml.safe_load(TRUTH.read_text())
    expected = defaultdict(set)
    for g in truth["gaps"]:
        expected[g["kind"]].add(_norm(g["kind"], g["subject"]))
    found = defaultdict(set)
    for g in gaps:
        found[g["gap_kind"]].add(_norm(g["gap_kind"], g["subject"]))
    out = {}
    for kind in sorted(set(expected) | set(found)):
        e, f = expected[kind], found[kind]
        tp = len(e & f)
        out[kind] = {"expected": len(e), "found": len(f), "true_positives": tp,
                     "precision": round(tp / len(f), 3) if f else (1.0 if not e else 0.0),
                     "recall": round(tp / len(e), 3) if e else (1.0 if not f else 0.0),
                     "missed": sorted(e - f)[:10], "spurious": sorted(f - e)[:10]}
    return out


def policy_key_share(rec: dict, since: str | None = None, until: str | None = None) -> dict:
    """What the answer key says: of the requests a person approved in [since, until), the share Contoso's
    unwritten policies cover. The same basis as policy.avoidable, so the two compare."""
    from shopfloor.seed.world import DATASETS, covered_by_policy
    roles = {title: key for key, (title, _) in ROLES.items()}
    titles = {a["id"]: a.get("title") for a in rec["actors"]}
    ds = {d[0]: d for d in DATASETS}
    rejected = {t["request"] for t in rec["tasks"] if t["step"] == "st-approve" and t["outcome"]["status"] != "accepted"}
    total = covered = 0
    for r in rec["requests"]:
        d = ds.get(r.get("dataset"))
        if not d or r["id"] in rejected or (since and r["requested_at"] < since) or (until and r["requested_at"] >= until):
            continue
        total += 1
        covered += bool(covered_by_policy(roles.get(titles.get(r.get("on_behalf_of"))), d, r.get("privilege")))
    return {"requests_approved": total, "covered": covered, "share": round(covered / total, 3) if total else 0.0}


def beyond_key(rec: dict, policies: list[dict], since: str | None = None, until: str | None = None) -> int:
    """Requests in [since, until) the derived policies would grant that the answer key's policies would not:
    access granted without a request where Contoso's practice still asked a person."""
    from shopfloor.cleanup import slug
    from shopfloor.policy import covers
    from shopfloor.seed.world import DATASETS, covered_by_policy
    roles = {title: key for key, (title, _) in ROLES.items()}
    titles = {a["id"]: a.get("title") for a in rec["actors"]}
    ds = {d[0]: d for d in DATASETS}
    vocab_ds = {d["id"]: d for d in rec["datasets"]}
    n = 0
    for r in rec["requests"]:
        d = ds.get(r.get("dataset"))
        if not d or (since and r["requested_at"] < since) or (until and r["requested_at"] >= until):
            continue
        title = titles.get(r.get("on_behalf_of"))
        ours = any(covers(p, slug(title), vocab_ds[d[0]], r.get("privilege")) for p in policies)
        n += ours and not covered_by_policy(roles.get(title), d, r.get("privilege"))
    return n
