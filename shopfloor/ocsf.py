"""OCSF: gaps and stops projected into OCSF events, driven by the SSSOM mapping set.

Checked by OCSF's own validator (the OCSF schema server's `/api/v2/validate`).
"""

import json
import time
import urllib.request
from datetime import datetime, timezone
from functools import cache

import yaml

from shopfloor.mappings import read_sssom
from shopfloor.otel import span_attributes
from shopfloor.vocab import ROOT

MAPPINGS = ROOT / "mappings"
VALIDATOR = "https://schema.ocsf.io/api/v2/validate"


@cache
def _spec() -> dict:
    return yaml.safe_load((MAPPINGS / "ocsf-projection.yaml").read_text())


@cache
def _rows() -> list[dict]:
    return read_sssom(MAPPINGS / "ocsf.sssom.tsv")


def _set(doc: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = doc
    for i, p in enumerate(parts):
        last = i == len(parts) - 1
        if p.endswith("[]"):
            key = p[:-2]
            arr = cur.setdefault(key, [])
            if last:
                arr.append(value)
                return
            if not arr:
                arr.append({})
            cur = arr[-1]
        elif last:
            cur[p] = value
        else:
            cur = cur.setdefault(p, {})


def _epoch_ms(v) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return int(v.timestamp() * 1000)
    return int(time.time() * 1000)


def project(cls: str, obj: dict, decision: dict | None = None) -> dict:
    """Project a Gap or a WorkEvent into an OCSF event. `decision` carries the rule for a stop."""
    spec = _spec()
    c = spec["classes"][cls]
    doc = {
        "class_uid": c["class_uid"], "category_uid": c["category_uid"], "activity_id": c["activity_id"],
        "type_uid": c["class_uid"] * 100 + c["activity_id"],
        "time": _epoch_ms(obj.get("at")),
        "severity_id": c["severity_by"]["values"].get(obj.get(c["severity_by"]["field"]), 1),
        "metadata": {"version": spec["ocsf_version"], "product": dict(spec["product"])},
        "finding_info": {"title": c["title"].format(**{k: obj.get(k, "") for k in ("gap_kind", "kind")})},
        "compliance": {"status_id": c["compliance_status_id"]},
    }
    mapped = set()
    sources = [(cls, obj)] + ([("Decision", decision)] if decision else [])
    for owner, data in sources:
        for row in _rows():
            subj_cls, _, slot = row["subject_id"].removeprefix("work:").partition(".")
            if subj_cls != owner or slot not in data or data[slot] is None:
                continue
            path = row["object_id"].removeprefix("ocsf:")
            value = _epoch_ms(data[slot]) if path == "time" else data[slot]
            _set(doc, path, value)
            mapped.add((owner, slot))
    # Whatever has no OCSF home keeps its OpenTelemetry name in `unmapped`, so the SOC can still join on it.
    unmapped = {}
    for owner, data in sources:
        for a in span_attributes(owner, {k: v for k, v in data.items() if (owner, k) not in mapped}):
            unmapped[a["name"]] = a["value"]
    if unmapped:
        doc["unmapped"] = unmapped
    return doc


def validate(event: dict) -> dict:
    """Ask OCSF's own validator. Returns its response: errors, warnings and counts."""
    req = urllib.request.Request(VALIDATOR, data=json.dumps(event).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

