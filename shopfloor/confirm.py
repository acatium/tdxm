"""The approve step of the loop: proposals, and a person's confirmations of them.

Every change (a repair, a declared policy, an autonomy promotion) is first a proposal. Its id carries a digest
of its content, so a confirmation covers exactly what was proposed; if the proposal changes, it needs a new
one. Confirmations live in data/confirmations.yaml as instances of the vocabulary's Confirmation class. In a
deployment a person writes that file. In the demo, `make scenario` writes labelled stand-ins for Contoso's
process owner, like the scripted approvers in chat; nothing else in this repository writes it.
"""

import hashlib
import json
from pathlib import Path

import yaml

from shopfloor import store
from shopfloor.vocab import ROOT

CONFIRMATIONS = ROOT / "data" / "confirmations.yaml"


def proposal_id(change_kind: str, name: str, content) -> str:
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return f"{change_kind}:{name}:{digest}"


def load(path: Path = CONFIRMATIONS) -> list[dict]:
    """The confirmations a person has written. Missing file: none. A file that does not conform fails loudly."""
    if not path.exists():
        return []
    items = (yaml.safe_load(path.read_text()) or {}).get("confirmations") or []
    for c in items:  # YAML reads a timestamp as a datetime; the vocabulary wants ISO 8601
        v = c.get("decided_at")
        if hasattr(v, "isoformat"):
            c["decided_at"] = v.isoformat().replace("+00:00", "Z")
    errors = store.check({"confirmations": [{k: v for k, v in c.items() if v is not None} for c in items]})
    if errors:
        raise ValueError(f"{path.name} does not conform to the vocabulary: {errors[:5]}")
    return items


def verdict(confirmations: list[dict], pid: str, decided_by: set[str] | None = None) -> str | None:
    """approve, reject, or None if nobody has decided. Any rejection wins, from anyone, whatever the order. When
    decided_by is given, only an approval naming one of those people counts; the demo does not verify who wrote
    it."""
    mine = [c for c in confirmations if c["id"] == pid]
    if any(c["verdict"] == "reject" for c in mine):
        return "reject"
    if any(c["verdict"] == "approve" and (decided_by is None or c["decided_by"] in decided_by) for c in mine):
        return "approve"
    return None


def proposal(change_kind: str, name: str, content, summary: str, evidence, needs: str | None = None) -> dict:
    p = {"id": proposal_id(change_kind, name, content), "change_kind": change_kind, "summary": summary,
         "evidence": evidence}
    if needs:
        p["needs"] = needs
    return p


def template(proposals: list[dict]) -> str:
    """A starting point for the person: every open proposal, with the fields to fill in, commented out."""
    lines = ["# Confirm or reject each proposal: uncomment it, set verdict, decided_by and decided_at.",
             "# Written by a person. A proposal whose content changes gets a new id and needs a new decision.",
             "confirmations:"]
    for p in proposals:
        lines += [f"# {p['summary']}"]
        if p.get("needs"):
            lines += [f"# Needs: {p['needs']}"]
        lines += [f"#- id: {p['id']}", f"#  change_kind: {p['change_kind']}", "#  verdict: approve   # or reject",
                  "#  decided_by: <your name>", "#  decided_at: 2026-11-01T09:00:00Z", "#  reason: <why>", ""]
    return "\n".join(lines) + "\n"
